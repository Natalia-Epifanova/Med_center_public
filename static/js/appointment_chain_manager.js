class AppointmentChainManager {
    constructor(options = {}) {
        this.csrfToken = options.csrfToken;
        this.mainDoctorId = options.mainDoctorId;
        this.mainDate = options.mainDate;
        this.maxAdditionalAppointments = options.maxAdditionalAppointments || 5;

        this.additionalAppointments = [];
        this.appointmentForms = [];
        this.proceduralAppointments = []; // Храним данные о процедурных записях

        this.init();
    }

    init() {
        this.bindEvents();
        this.renderInitialTemplate();
    }

    bindEvents() {
        // Слушаем изменение типа записи
        document.querySelectorAll('input[name="appointment_chain_type"]').forEach(radio => {
            radio.addEventListener('change', (e) => this.onChainTypeChange(e.target.value));
        });

        // Инициализируем начальное состояние
        const initialType = document.querySelector('input[name="appointment_chain_type"]:checked');
        if (initialType) {
            this.onChainTypeChange(initialType.value);
        }
    }

    onChainTypeChange(type) {
        console.log('Chain type changed to:', type);

        // Скрываем все секции
        this.hideAllSections();

        // Показываем нужную секцию только если она существует
        switch(type) {
            case 'additional':
                const additionalSection = document.getElementById('additionalServiceSection');
                const sameDoctorSections = document.getElementById('sameDoctorSections');
                if (additionalSection) additionalSection.style.display = 'block';
                if (sameDoctorSections) sameDoctorSections.style.display = 'block';
                break;

            case 'two_slots':
                const twoSlotsSection = document.getElementById('twoSlotsSection');
                const sameDoctorSections2 = document.getElementById('sameDoctorSections');
                if (twoSlotsSection) twoSlotsSection.style.display = 'block';
                if (sameDoctorSections2) sameDoctorSections2.style.display = 'block';
                break;

            case 'another_doctor':
                const anotherDoctorSection = document.getElementById('anotherDoctorSection');
                if (anotherDoctorSection) {
                    anotherDoctorSection.style.display = 'block';
                    this.loadAnotherDoctorForm();
                }
                break;

            case 'multiple':
                const multipleSection = document.getElementById('multipleAppointmentsSection');
                if (multipleSection) {
                    multipleSection.style.display = 'block';
                    this.addAppointmentForm();
                }
                break;
        }
    }

    hideAllSections() {
        const sections = [
            'sameDoctorSections',
            'additionalServiceSection',
            'twoSlotsSection',
            'anotherDoctorSection',
            'multipleAppointmentsSection'
        ];

        sections.forEach(sectionId => {
            const section = document.getElementById(sectionId);
            if (section) {
                section.style.display = 'none';
            }
        });
    }

    renderInitialTemplate() {
        // Шаблон для формы дополнительной записи с кнопкой процедурного кабинета
        this.appointmentFormTemplate = `
            <div class="appointment-form-card card mb-3" data-form-index="{index}">
                <div class="card-header bg-light d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">Запись к врачу #{index}</h6>
                    <button type="button" class="btn btn-outline-danger btn-sm remove-form" data-index="{index}">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-4">
                            <label class="form-label">Врач *</label>
                            <select class="form-select doctor-select" data-index="{index}" required>
                                <option value="">Выберите врача...</option>
                            </select>
                            <div class="invalid-feedback">Выберите врача</div>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Услуга *</label>
                            <select class="form-select service-select" data-index="{index}" disabled required>
                                <option value="">Сначала выберите врача</option>
                            </select>
                            <div class="invalid-feedback">Выберите услугу</div>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Дата *</label>
                            <input type="date" class="form-control date-select" data-index="{index}" required>
                            <div class="invalid-feedback">Выберите дату</div>
                        </div>
                    </div>
                    <div class="row mt-3">
                        <div class="col-md-6">
                            <label class="form-label">Время *</label>
                            <select class="form-select slot-select" data-index="{index}" disabled required>
                                <option value="">Сначала выберите врача и дату</option>
                            </select>
                            <div class="invalid-feedback">Выберите время</div>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Комментарий</label>
                            <textarea class="form-control comment-input" data-index="{index}" rows="2"
                                      placeholder="Необязательный комментарий"></textarea>
                        </div>
                    </div>

                    <!-- КНОПКА ПРОЦЕДУРНОГО КАБИНЕТА ДЛЯ ЭТОЙ ФОРМЫ -->
                    <div class="row mt-3">
                        <div class="col-12">
                            <div class="form-check">
                                <input type="checkbox" class="form-check-input procedural-checkbox"
                                       data-index="{index}" id="procedural_{index}">
                                <label class="form-check-label" for="procedural_{index}">
                                    <i class="fas fa-syringe"></i> Занять окошко в процедурном кабинете
                                </label>
                                <div class="form-text">
                                    Автоматически займет такое же время в процедурном кабинете
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="row mt-2">
                        <div class="col-12">
                            <div class="form-text">
                                Врач: <span class="doctor-name text-muted">не выбран</span> |
                                Дата: <span class="appointment-date text-muted">не выбрана</span> |
                                Время: <span class="appointment-time text-muted">не выбрано</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    addAppointmentForm() {
        const container = document.getElementById('multipleAppointmentsContainer');
        if (!container) {
            console.error('Container multipleAppointmentsContainer not found');
            return;
        }

        // Проверяем лимит
        if (this.additionalAppointments.length >= this.maxAdditionalAppointments) {
            alert(`Максимум можно добавить ${this.maxAdditionalAppointments} дополнительных записей`);
            return;
        }

        const index = this.additionalAppointments.length + 1;
        const formHtml = this.appointmentFormTemplate.replace(/{index}/g, index);

        const formElement = document.createElement('div');
        formElement.innerHTML = formHtml;
        container.appendChild(formElement);

        // Инициализируем форму
        this.initAppointmentForm(index);
    }

    initAppointmentForm(index) {
        const formElement = document.querySelector(`[data-form-index="${index}"]`);
        if (!formElement) {
            console.error(`Form element with index ${index} not found`);
            return;
        }

        // Загружаем список врачей (исключая основного)
        this.loadDoctorsForForm(index);

        // Устанавливаем минимальную дату
        const dateInput = formElement.querySelector('.date-select');
        const today = new Date().toISOString().split('T')[0];
        dateInput.min = today;
        dateInput.value = this.mainDate || today;

        // Находим чекбокс процедурного кабинета и селектор услуг
        const proceduralCheckbox = formElement.querySelector('.procedural-checkbox');
        const serviceSelect = formElement.querySelector('.service-select');

        // Добавляем обработчик для автоматического выделения процедурного кабинета
        if (serviceSelect && proceduralCheckbox) {
            serviceSelect.addEventListener('change', function() {
                // Используем утилиту для проверки медикаментозных блокад
                if (window.AppointmentUtils && window.AppointmentUtils.ProceduralManager) {
                    window.AppointmentUtils.ProceduralManager.updateProceduralCheckbox(this, proceduralCheckbox);
                } else {
                    // Фолбэк проверка
                    const selectedOption = this.options[this.selectedIndex];
                    const serviceName = selectedOption ? selectedOption.text.toLowerCase() : '';
                    const blockadeKeywords = ['блокад', 'введение', 'инъекц', 'укол', 'инфузи', 'пункц'];

                    if (blockadeKeywords.some(keyword => serviceName.includes(keyword))) {
                        proceduralCheckbox.checked = true;
                        console.log('Auto-checked procedural for medical blockade');

                        // Вызываем событие change чтобы обновились данные
                        proceduralCheckbox.dispatchEvent(new Event('change'));
                    }
                }
            });
        }

        // Привязываем события
        this.bindFormEvents(index);

        // Добавляем в массив форм
        this.appointmentForms.push(index);

        // Триггерим загрузку слотов если дата уже установлена
        if (this.mainDate) {
            setTimeout(() => {
                this.onDateSelect(index, this.mainDate);
            }, 100);
        }
    }

    async loadDoctorsForForm(index) {
        try {
            // Проверяем, есть ли API endpoint
            const response = await fetch('/appointments/api/available-doctors/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    exclude_doctor_id: this.mainDoctorId
                })
            });

            if (!response.ok) {
                console.error('Failed to load doctors:', response.status);
                return;
            }

            const data = await response.json();

            if (data.success) {
                const formElement = document.querySelector(`[data-form-index="${index}"]`);
                if (!formElement) return;

                const doctorSelect = formElement.querySelector('.doctor-select');

                // Очищаем и заполняем список врачей
                doctorSelect.innerHTML = '<option value="">Выберите врача...</option>';

                data.doctors.forEach(doctor => {
                    const option = document.createElement('option');
                    option.value = doctor.id;
                    option.textContent = `${doctor.surname} ${doctor.first_name[0]}.${doctor.last_name[0]}. (${doctor.specialization})`;
                    doctorSelect.appendChild(option);
                });
            } else {
                console.error('Failed to load doctors:', data.error);
            }
        } catch (error) {
            console.error('Error loading doctors:', error);
            // Если API не работает, используем fallback
            this.loadDoctorsFallback(index);
        }
    }

    loadDoctorsFallback(index) {
        const formElement = document.querySelector(`[data-form-index="${index}"]`);
        if (!formElement) return;

        const doctorSelect = formElement.querySelector('.doctor-select');
        doctorSelect.innerHTML = '<option value="">Загрузка врачей...</option>';

        // Можно добавить fallback или сообщение об ошибке
        setTimeout(() => {
            doctorSelect.innerHTML = '<option value="">Не удалось загрузить врачей. Проверьте соединение.</option>';
        }, 2000);
    }

    // Методы для типа "another_doctor" (одна дополнительная запись)
    loadAnotherDoctorForm() {
        const container = document.getElementById('anotherDoctorFormContainer');
        if (!container) {
            console.error('Container anotherDoctorFormContainer not found');
            return;
        }

        // Очищаем контейнер
        container.innerHTML = '';

        // Создаем новую форму
        const formHtml = this.appointmentFormTemplate.replace(/{index}/g, 'single');
        container.innerHTML = formHtml;

        // Инициализируем форму
        this.initAppointmentForm('single');

        // Показываем кнопку для добавления еще одной записи
        const addAnotherBtn = document.getElementById('addAnotherAppointmentBtn');
        if (addAnotherBtn) {
            addAnotherBtn.style.display = 'block';
        }
    }

    // Метод для добавления еще одного врача (переход к multiple)
    addAnotherDoctorForm() {
        // Меняем тип на multiple
        const multipleRadio = document.querySelector('input[name="appointment_chain_type"][value="multiple"]');
        if (multipleRadio) {
            multipleRadio.checked = true;
            this.onChainTypeChange('multiple');
        }
    }

    // Обновляем скрытое поле с данными
    updateHiddenField() {
        const hiddenField = document.getElementById('id_additional_appointments_data');
        if (hiddenField) {
            // Сохраняем только валидные данные
            const validAppointments = this.additionalAppointments.filter(app =>
                app.doctor_id && app.service_id && app.date && app.time_slot_id
            );

            hiddenField.value = JSON.stringify(validAppointments);
        }
    }

    // Обновление скрытого поля с процедурными данными
    updateProceduralHiddenField() {
        const hiddenField = document.getElementById('id_procedural_appointments_data');
        if (!hiddenField) {
            console.warn('Hidden field for procedural data not found - creating it dynamically');

            // Создаем скрытое поле динамически
            const newField = document.createElement('input');
            newField.type = 'hidden';
            newField.id = 'id_procedural_appointments_data';
            newField.name = 'procedural_appointments_data';

            // Добавляем его в форму
            const form = document.getElementById('appointmentForm');
            if (form) {
                form.appendChild(newField);
            } else {
                console.error('Cannot find appointment form');
                return;
            }
        }

        // Теперь поле должно существовать
        const field = document.getElementById('id_procedural_appointments_data');
        if (!field) {
            console.error('Failed to create procedural data field');
            return;
        }

        // Сохраняем только валидные данные (все поля заполнены)
        const validData = this.proceduralAppointments.filter(item =>
            item.needs_procedural === true &&
            item.appointment_data &&
            item.appointment_data.doctor_id &&
            item.appointment_data.service_id &&
            item.appointment_data.date &&
            item.appointment_data.time_slot_id
        );

        console.log('Saving procedural data to hidden field:', validData);
        field.value = JSON.stringify(validData);
    }

    // Метод для обработки процедурных записей
    saveProceduralData(index, needsProcedural) {
        // Находим данные формы
        const formData = this.getFormData(index);
        if (!formData) {
            console.error(`Cannot get form data for index ${index}`);
            return;
        }

        // Проверяем, все ли обязательные поля заполнены для процедурной записи
        const isValidForProcedural = formData.doctor_id &&
                                      formData.service_id &&
                                      formData.date &&
                                      formData.time_slot_id;

        if (!isValidForProcedural) {
            console.log(`Form data for index ${index} is not complete for procedural`, formData);
            // Удаляем запись если она была добавлена ранее
            const existingIndex = this.proceduralAppointments.findIndex(
                item => item.index == index
            );
            if (existingIndex >= 0) {
                this.proceduralAppointments.splice(existingIndex, 1);
            }
            this.updateProceduralHiddenField();
            return;
        }

        // Проверяем, есть ли уже запись для этого индекса
        const existingIndex = this.proceduralAppointments.findIndex(
            item => item.index == index
        );

        if (existingIndex >= 0) {
            // Обновляем существующую запись
            this.proceduralAppointments[existingIndex] = {
                ...this.proceduralAppointments[existingIndex],
                needs_procedural: needsProcedural,
                appointment_data: formData
            };
        } else {
            // Создаем новую запись
            this.proceduralAppointments.push({
                index: index,
                needs_procedural: needsProcedural,
                appointment_data: formData
            });
        }

        console.log(`Saved procedural data for index ${index}:`, {
            needs_procedural: needsProcedural,
            appointment_data: formData
        });

        this.updateProceduralHiddenField();
    }

    // Валидация перед отправкой
    validateBeforeSubmit() {
        const chainTypeElement = document.querySelector('input[name="appointment_chain_type"]:checked');
        if (!chainTypeElement) {
            alert('Пожалуйста, выберите тип записи');
            return false;
        }

        const chainType = chainTypeElement.value;

        // Обновляем все скрытые поля перед валидацией
        this.updateHiddenField();
        this.updateProceduralHiddenField();

        if (chainType === 'another_doctor') {
            // Проверяем форму single
            if (!this.validateForm('single')) {
                alert('Пожалуйста, заполните все обязательные поля для дополнительной записи');
                return false;
            }

            // Проверяем, что есть данные
            const formData = this.getFormData('single');
            if (!formData || !formData.doctor_id || !formData.service_id || !formData.date || !formData.time_slot_id) {
                alert('Пожалуйста, заполните все обязательные поля для дополнительной записи');
                return false;
            }

            return true;
        } else if (chainType === 'multiple') {
            // Проверяем все формы
            if (this.appointmentForms.length === 0) {
                alert('Добавьте хотя бы одну дополнительную запись');
                return false;
            }

            let allValid = true;
            let hasValidAppointment = false;

            this.appointmentForms.forEach(index => {
                if (this.validateForm(index)) {
                    const formData = this.getFormData(index);
                    if (formData && formData.doctor_id && formData.service_id &&
                        formData.date && formData.time_slot_id) {
                        hasValidAppointment = true;
                    }
                } else {
                    allValid = false;
                }
            });

            if (!allValid) {
                alert('Пожалуйста, заполните все обязательные поля для дополнительных записей');
                return false;
            }

            if (!hasValidAppointment) {
                alert('Добавьте хотя бы одну корректно заполненную дополнительную запись');
                return false;
            }

            return true;
        }

        return true;
    }

    validateForm(index) {
        const formElement = document.querySelector(`[data-form-index="${index}"]`);
        if (!formElement) return false;

        const requiredFields = formElement.querySelectorAll('select[required], input[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            if (!field.value) {
                field.classList.add('is-invalid');
                isValid = false;
            } else {
                field.classList.remove('is-invalid');
            }
        });

        return isValid;
    }
    removeAppointmentForm(index) {
        // Удаляем элемент из DOM
        const formElement = document.querySelector(`[data-form-index="${index}"]`);
        if (formElement) {
            formElement.remove();
        }

        // Удаляем из массива форм
        const formIndex = this.appointmentForms.indexOf(index);
        if (formIndex > -1) {
            this.appointmentForms.splice(formIndex, 1);
        }

        // Удаляем из дополнительных записей
        const appointmentIndex = this.additionalAppointments.findIndex(app => app.index === index);
        if (appointmentIndex > -1) {
            this.additionalAppointments.splice(appointmentIndex, 1);
        }

        // Удаляем из процедурных записей
        const proceduralIndex = this.proceduralAppointments.findIndex(item => item.index == index);
        if (proceduralIndex > -1) {
            this.proceduralAppointments.splice(proceduralIndex, 1);
        }

        // Обновляем скрытые поля
        this.updateHiddenField();
        this.updateProceduralHiddenField();

        console.log(`Removed appointment form with index ${index}`);
    }

    // Метод для получения данных формы
    getFormData(index) {
        const formElement = document.querySelector(`[data-form-index="${index}"]`);
        if (!formElement) return null;

        const doctorSelect = formElement.querySelector('.doctor-select');
        const serviceSelect = formElement.querySelector('.service-select');
        const dateInput = formElement.querySelector('.date-select');
        const slotSelect = formElement.querySelector('.slot-select');
        const commentInput = formElement.querySelector('.comment-input');

        return {
            doctor_id: doctorSelect ? doctorSelect.value : null,
            service_id: serviceSelect ? serviceSelect.value : null,
            date: dateInput ? dateInput.value : null,
            time_slot_id: slotSelect ? slotSelect.value : null,
            comment: commentInput ? commentInput.value : null
        };
    }
}

// Добавляем методы для работы с формами
AppointmentChainManager.prototype.bindFormEvents = function(index) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) return;

    // Выбор врача
    const doctorSelect = formElement.querySelector('.doctor-select');
    doctorSelect.addEventListener('change', (e) => this.onDoctorSelect(index, e.target.value));

    // Выбор даты
    const dateInput = formElement.querySelector('.date-select');
    dateInput.addEventListener('change', (e) => this.onDateSelect(index, e.target.value));

    // Выбор времени
    const slotSelect = formElement.querySelector('.slot-select');
    slotSelect.addEventListener('change', (e) => this.onSlotSelect(index, e.target.value));

    // Удаление формы
    const removeBtn = formElement.querySelector('.remove-form');
    if (removeBtn) {
        removeBtn.addEventListener('click', () => this.removeAppointmentForm(index));
    }

    // Изменение комментария
    const commentInput = formElement.querySelector('.comment-input');
    commentInput.addEventListener('input', (e) => this.onCommentChange(index, e.target.value));

    // Изменение чекбокса процедурного кабинета
    const proceduralCheckbox = formElement.querySelector('.procedural-checkbox');
    if (proceduralCheckbox) {
        proceduralCheckbox.addEventListener('change', (e) => {
            this.saveProceduralData(index, e.target.checked);
        });

        // Сразу проверяем чекбокс при инициализации если он уже отмечен
        if (proceduralCheckbox.checked) {
            this.saveProceduralData(index, true);
        }
    }
};

AppointmentChainManager.prototype.onDoctorSelect = async function(index, doctorId) {
    if (!doctorId) return;

    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) return;

    const serviceSelect = formElement.querySelector('.service-select');
    const doctorNameSpan = formElement.querySelector('.doctor-name');

    // Загружаем услуги врача
    try {
        const response = await fetch('/appointments/api/doctor-services/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify({ doctor_id: doctorId })
        });

        const data = await response.json();
        console.log('Doctor services API response:', data);

        if (data.success) {
            // Обновляем имя врача
            if (doctorNameSpan && data.doctor) {
                doctorNameSpan.textContent = data.doctor.name;
            }

            // Заполняем список услуг
            serviceSelect.innerHTML = '<option value="">Выберите услугу...</option>';
            data.services.forEach(service => {
                const option = document.createElement('option');
                option.value = service.id;
                option.textContent = `${service.name} (${service.price} руб.)`;
                option.dataset.price = service.price;
                serviceSelect.appendChild(option);
            });

            serviceSelect.disabled = false;

            // АВТОМАТИЧЕСКИ ЗАГРУЖАЕМ СЛОТЫ ЕСЛИ ДАТА УЖЕ ВЫБРАНА
            const dateInput = formElement.querySelector('.date-select');
            if (dateInput && dateInput.value) {
                console.log('Auto-loading slots for date:', dateInput.value);
                this.onDateSelect(index, dateInput.value);
            }
        }
    } catch (error) {
        console.error('Error loading services:', error);
    }
};

AppointmentChainManager.prototype.onDateSelect = async function(index, date) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) {
        console.error(`Form element for index ${index} not found`);
        return;
    }

    const doctorSelect = formElement.querySelector('.doctor-select');
    const slotSelect = formElement.querySelector('.slot-select');
    const dateSpan = formElement.querySelector('.appointment-date');

    const doctorId = doctorSelect.value;

    if (!doctorId || !date) {
        console.log(`Missing doctorId (${doctorId}) or date (${date})`);
        return;
    }

    console.log(`Loading slots for doctor ${doctorId}, date ${date}`);

    // Обновляем отображение даты
    if (dateSpan) {
        const formattedDate = new Date(date + 'T00:00:00').toLocaleDateString('ru-RU');
        dateSpan.textContent = formattedDate;
    }

    // Загружаем доступные слоты
    try {
        const response = await fetch('/appointments/api/available-slots-for-doctor/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify({
                doctor_id: doctorId,
                date: date
            })
        });

        if (!response.ok) {
            console.error('Failed to load slots:', response.status);
            slotSelect.innerHTML = '<option value="">Ошибка загрузки слотов</option>';
            slotSelect.disabled = true;
            return;
        }

        const data = await response.json();
        console.log('Slots API response:', data);

        if (data.success) {
            slotSelect.innerHTML = '<option value="">Выберите время...</option>';

            if (data.slots && data.slots.length > 0) {
                console.log(`Found ${data.slots.length} available slots`);
                data.slots.forEach(slot => {
                    const option = document.createElement('option');
                    option.value = slot.id;
                    option.textContent = `${slot.time} (${slot.cabinet})`;
                    option.dataset.time = slot.time;
                    slotSelect.appendChild(option);
                });

                slotSelect.disabled = false;
            } else {
                console.log('No available slots found');
                slotSelect.innerHTML = '<option value="">Нет доступных слотов на эту дату</option>';
                slotSelect.disabled = true;
            }
        } else {
            console.error('API returned success=false:', data.error);
            slotSelect.innerHTML = '<option value="">Ошибка загрузки слотов</option>';
            slotSelect.disabled = true;
        }
    } catch (error) {
        console.error('Error loading slots:', error);
        slotSelect.innerHTML = '<option value="">Ошибка загрузки слотов</option>';
        slotSelect.disabled = true;
    }
};

AppointmentChainManager.prototype.onSlotSelect = function(index, slotId) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    const slotSelect = formElement.querySelector('.slot-select');
    const timeSpan = formElement.querySelector('.appointment-time');

    if (slotId && timeSpan) {
        const selectedOption = slotSelect.options[slotSelect.selectedIndex];
        if (selectedOption && selectedOption.dataset.time) {
            timeSpan.textContent = selectedOption.dataset.time;
        }
    }

    // Сохраняем данные формы
    this.saveFormData(index);
};

AppointmentChainManager.prototype.saveFormData = function(index) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) return;

    const doctorSelect = formElement.querySelector('.doctor-select');
    const serviceSelect = formElement.querySelector('.service-select');
    const dateInput = formElement.querySelector('.date-select');
    const slotSelect = formElement.querySelector('.slot-select');
    const commentInput = formElement.querySelector('.comment-input');
    const proceduralCheckbox = formElement.querySelector('.procedural-checkbox');

    // Создаем объект данных
    const appointmentData = {
        doctor_id: doctorSelect ? doctorSelect.value : null,
        service_id: serviceSelect ? serviceSelect.value : null,
        date: dateInput ? dateInput.value : null,
        time_slot_id: slotSelect ? slotSelect.value : null,
        comment: commentInput ? commentInput.value : null
    };

    // Проверяем, все ли обязательные поля заполнены
    const isValid = appointmentData.doctor_id &&
                   appointmentData.service_id &&
                   appointmentData.date &&
                   appointmentData.time_slot_id;

    // Обновляем или добавляем данные в дополнительные записи
    const existingIndex = this.additionalAppointments.findIndex(app => app.index === index);

    if (isValid) {
        if (existingIndex >= 0) {
            this.additionalAppointments[existingIndex] = {
                index: index,
                ...appointmentData
            };
        } else {
            this.additionalAppointments.push({
                index: index,
                ...appointmentData
            });
        }

        // Валидируем форму
        formElement.classList.remove('border-danger');

        // ОБНОВЛЯЕМ ПРОЦЕДУРНЫЕ ДАННЫЕ если чекбокс отмечен
        if (proceduralCheckbox && proceduralCheckbox.checked) {
            this.saveProceduralData(index, true);
        }
    } else {
        // Удаляем невалидные данные
        if (existingIndex >= 0) {
            this.additionalAppointments.splice(existingIndex, 1);
        }

        // Помечаем невалидную форму
        formElement.classList.add('border-danger');

        // Удаляем процедурные данные если форма невалидна
        const proceduralIndex = this.proceduralAppointments.findIndex(
            item => item.index == index
        );
        if (proceduralIndex >= 0) {
            this.proceduralAppointments.splice(proceduralIndex, 1);
            this.updateProceduralHiddenField();
        }
    }

    // Обновляем скрытые поля
    this.updateHiddenField();
    this.updateProceduralHiddenField();
};

// Экспорт для использования
window.AppointmentChainManager = AppointmentChainManager;