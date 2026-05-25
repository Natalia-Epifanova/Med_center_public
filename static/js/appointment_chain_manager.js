/**
 * Менеджер цепочек записей для работы с дополнительными записями к разным врачам
 */
class AppointmentChainManager {
    constructor(options = {}) {
        this.csrfToken = options.csrfToken;
        this.mainDoctorId = options.mainDoctorId;
        this.mainDate = options.mainDate;
        this.maxAdditionalAppointments = options.maxAdditionalAppointments || 5;

        this.additionalAppointments = [];
        this.appointmentForms = [];
        this.proceduralAppointments = [];

        this.bookedSlots = new Set();
        this.mainAppointmentSlot = null;
        this.allBookedSlots = [];

        this.init();
    }

    init() {
        this.bindEvents();
        this.renderInitialTemplate();
        this.setMainAppointmentSlot();
    }

    setMainAppointmentSlot() {
        if (!window.originalDate) {
            const hiddenDate = document.getElementById('js-original-date');
            if (hiddenDate) window.originalDate = hiddenDate.value;
        }

        if (!window.originalTime) {
            const hiddenTime = document.getElementById('js-original-time');
            if (hiddenTime) window.originalTime = hiddenTime.value;
        }

        if (!window.currentSlotId) {
            const hiddenSlotId = document.getElementById('js-current-slot-id');
            if (hiddenSlotId) window.currentSlotId = parseInt(hiddenSlotId.value);
        }

        if (!window.currentSlotId || !window.originalTime || !window.originalDate) {
            const urlParams = new URLSearchParams(window.location.search);
            const dateFromUrl = urlParams.get('date');
            if (dateFromUrl && !window.originalDate) window.originalDate = dateFromUrl;
            return;
        }

        const timeMatch = window.originalTime.match(/(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})/);
        if (timeMatch) {
            const formatTime = (hours, minutes) => {
                const h = hours.padStart(2, '0');
                const m = minutes.padStart(2, '0');
                return `${h}:${m}:00`;
            };

            this.mainAppointmentSlot = {
                id: window.currentSlotId,
                startTime: formatTime(timeMatch[1], timeMatch[2]),
                endTime: formatTime(timeMatch[3], timeMatch[4]),
                display: window.originalTime,
                date: window.originalDate
            };

            this.bookedSlots.add(window.currentSlotId.toString());
        }
    }

    getMainAppointmentTime() {
        if (!this.mainAppointmentSlot) return null;
        return {
            start_time: this.mainAppointmentSlot.startTime,
            end_time: this.mainAppointmentSlot.endTime,
            time: this.mainAppointmentSlot.display
        };
    }

    checkSlotTimeOverlap(slotStart, slotEnd) {
        const mainTime = this.getMainAppointmentTime();
        if (!mainTime) return false;

        const mainStart = mainTime.start_time;
        const mainEnd = mainTime.end_time;

        if (slotStart === mainStart && slotEnd === mainEnd) return true;

        const timeToMinutes = (timeStr) => {
            const parts = timeStr.split(':');
            const hours = parseInt(parts[0], 10) || 0;
            const minutes = parseInt(parts[1], 10) || 0;
            const seconds = parts.length > 2 ? parseInt(parts[2], 10) || 0 : 0;
            return hours * 60 + minutes + seconds / 60;
        };

        const slotStartMinutes = timeToMinutes(slotStart);
        const slotEndMinutes = timeToMinutes(slotEnd);
        const mainStartMinutes = timeToMinutes(mainStart);
        const mainEndMinutes = timeToMinutes(mainEnd);

        return (
            (slotStartMinutes < mainEndMinutes && slotEndMinutes > mainStartMinutes) ||
            (slotStartMinutes >= mainStartMinutes && slotEndMinutes <= mainEndMinutes) ||
            (mainStartMinutes >= slotStartMinutes && mainEndMinutes <= slotEndMinutes)
        );
    }

    bindEvents() {
        document.querySelectorAll('input[name="appointment_chain_type"]').forEach(radio => {
            radio.addEventListener('change', (e) => this.onChainTypeChange(e.target.value));
        });

        const initialType = document.querySelector('input[name="appointment_chain_type"]:checked');
        if (initialType) this.onChainTypeChange(initialType.value);
    }

    onChainTypeChange(type) {
        this.hideAllSections();

        switch(type) {
            case 'additional':
                const additionalSection = document.getElementById('additionalServiceSection');
                const sameDoctorSections = document.getElementById('sameDoctorSections');
                if (additionalSection) additionalSection.style.display = 'block';
                if (sameDoctorSections) sameDoctorSections.style.display = 'block';

                // УДАЛЯЕМ старую форму "single" если она есть
                this.removeSingleFormIfExists();
                // УДАЛЯЕМ все формы "multiple"
                this.removeAllMultipleForms();
                break;

            case 'two_slots':
                const twoSlotsSection = document.getElementById('twoSlotsSection');
                const sameDoctorSections2 = document.getElementById('sameDoctorSections');
                if (twoSlotsSection) twoSlotsSection.style.display = 'block';
                if (sameDoctorSections2) sameDoctorSections2.style.display = 'block';

                // УДАЛЯЕМ старую форму "single" если она есть
                this.removeSingleFormIfExists();
                // УДАЛЯЕМ все формы "multiple"
                this.removeAllMultipleForms();
                break;

            case 'another_doctor':
                const anotherDoctorSection = document.getElementById('anotherDoctorSection');
                if (anotherDoctorSection) {
                    anotherDoctorSection.style.display = 'block';
                    this.loadAnotherDoctorForm();
                }

                // УДАЛЯЕМ все формы "multiple"
                this.removeAllMultipleForms();
                break;

            case 'multiple':
                const multipleSection = document.getElementById('multipleAppointmentsSection');
                if (multipleSection) {
                    multipleSection.style.display = 'block';

                    // УДАЛЯЕМ форму "single" если она есть
                    this.removeSingleFormIfExists();

                    // Добавляем форму только если еще нет форм
                    if (this.appointmentForms.length === 0) {
                        this.addAppointmentForm();
                    }
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
            if (section) section.style.display = 'none';
        });
    }

    renderInitialTemplate() {
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
                    <div class="col-md-4">
                        <label class="form-label">Тип оплаты *</label>
                        <select class="form-select insurance-select" data-index="{index}" required>
                            <option value="paid">Платный</option>
                            <option value="oms">ОМС</option>
                            <option value="dms">ДМС</option>
                        </select>
                        <div class="invalid-feedback">Выберите тип оплаты</div>
                    </div>
                    <div class="col-md-8">
                        <label class="form-label">Комментарий</label>
                        <textarea class="form-control comment-input" data-index="{index}" rows="2"
                                  placeholder="Необязательный комментарий"></textarea>
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
                        <!-- Оставьте пустым или добавьте другие поля -->
                    </div>
                </div>

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
        if (!container) return;

        if (this.additionalAppointments.length >= this.maxAdditionalAppointments) {
            alert(`Максимум можно добавить ${this.maxAdditionalAppointments} дополнительных записей`);
            return;
        }

        const index = this.additionalAppointments.length + 1;
        const formHtml = this.appointmentFormTemplate.replace(/{index}/g, index);

        const formElement = document.createElement('div');
        formElement.innerHTML = formHtml;
        container.appendChild(formElement);

        this.initAppointmentForm(index);
    }

    initAppointmentForm(index) {
        const formElement = document.querySelector(`[data-form-index="${index}"]`);
        if (!formElement) return;

        this.loadDoctorsForForm(index);

        const dateInput = formElement.querySelector('.date-select');
        const today = new Date().toISOString().split('T')[0];
        dateInput.min = today;
        dateInput.value = this.mainDate || today;

        const proceduralCheckbox = formElement.querySelector('.procedural-checkbox');
        const serviceSelect = formElement.querySelector('.service-select');

        if (serviceSelect && proceduralCheckbox) {
            serviceSelect.addEventListener('change', function() {
                if (window.AppointmentUtils && window.AppointmentUtils.ProceduralManager) {
                    window.AppointmentUtils.ProceduralManager.updateProceduralCheckbox(this, proceduralCheckbox);
                } else {
                    const selectedOption = this.options[this.selectedIndex];
                    const serviceName = selectedOption ? selectedOption.text.toLowerCase() : '';
                    const procedureKeywords = ['пункц', 'блокад', 'введение', 'инъекц', 'укол', 'инфузи'];

                    if (procedureKeywords.some(keyword => serviceName.includes(keyword))) {
                        proceduralCheckbox.checked = true;
                        proceduralCheckbox.dispatchEvent(new Event('change'));
                    }
                }
            });
        }

        this.bindFormEvents(index);
        this.appointmentForms.push(index);

        if (this.mainDate) {
            setTimeout(() => this.onDateSelect(index, this.mainDate), 100);
        }
    }

    async loadDoctorsForForm(index) {
        try {
            const response = await fetch('/appointments/api/available-doctors/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({ exclude_doctor_id: null  })
            });

            if (!response.ok) return;

            const data = await response.json();
            const formElement = document.querySelector(`[data-form-index="${index}"]`);
            if (!formElement || !data.success) return;

            const doctorSelect = formElement.querySelector('.doctor-select');
            doctorSelect.innerHTML = '<option value="">Выберите врача...</option>';

            data.doctors.forEach(doctor => {
                const option = document.createElement('option');
                option.value = doctor.id;
                option.textContent = doctor.display_name ||
                                     `${doctor.surname} ${doctor.first_name[0]}.${doctor.last_name[0]}. (${doctor.specialization_display})`;
                doctorSelect.appendChild(option);
            });
        } catch (error) {
            this.loadDoctorsFallback(index);
        }
    }

    loadDoctorsFallback(index) {
        const formElement = document.querySelector(`[data-form-index="${index}"]`);
        if (!formElement) return;

        const doctorSelect = formElement.querySelector('.doctor-select');
        doctorSelect.innerHTML = '<option value="">Загрузка врачей...</option>';

        setTimeout(() => {
            doctorSelect.innerHTML = '<option value="">Не удалось загрузить врачей. Проверьте соединение.</option>';
        }, 2000);
    }

    loadAnotherDoctorForm() {
        const container = document.getElementById('anotherDoctorFormContainer');
        if (!container) return;

        container.innerHTML = '';
        const formHtml = `
            <div class="appointment-form-card card mb-3" data-form-index="single">
                <div class="card-header bg-light d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">Запись к другому врачу</h6>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-4">
                            <label class="form-label">Врач *</label>
                            <select class="form-select doctor-select" data-index="single" required>
                                <option value="">Выберите врача...</option>
                            </select>
                            <div class="invalid-feedback">Выберите врача</div>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Услуга *</label>
                            <select class="form-select service-select" data-index="single" disabled required>
                                <option value="">Сначала выберите врача</option>
                            </select>
                            <div class="invalid-feedback">Выберите услугу</div>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Дата *</label>
                            <input type="date" class="form-control date-select" data-index="single" required>
                            <div class="invalid-feedback">Выберите дату</div>
                        </div>
                    </div>
                    <div class="row mt-3">
                        <div class="col-md-6">
                            <label class="form-label">Время *</label>
                            <select class="form-select slot-select" data-index="single" disabled required>
                                <option value="">Сначала выберите врача и дату</option>
                            </select>
                            <div class="invalid-feedback">Выберите время</div>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Комментарий</label>
                            <textarea class="form-control comment-input" data-index="single" rows="2"
                                      placeholder="Необязательный комментарий"></textarea>
                        </div>
                    </div>
                    <div class="row mt-3">
                        <div class="col-md-4">
                            <label class="form-label">Тип оплаты *</label>
                            <select class="form-select insurance-select" data-index="single" required>
                                <option value="paid">Платный</option>
                                <option value="oms">ОМС</option>
                                <option value="dms">ДМС</option>
                            </select>
                            <div class="invalid-feedback">Выберите тип оплаты</div>
                        </div>
                        <div class="col-md-8">
                            <label class="form-label">Комментарий</label>
                            <textarea class="form-control comment-input" data-index="single" rows="2"
                                      placeholder="Необязательный комментарий"></textarea>
                        </div>
                    </div>
                    <div class="row mt-3">
                        <div class="col-12">
                            <div class="form-check">
                                <input type="checkbox" class="form-check-input procedural-checkbox"
                                       data-index="single" id="procedural_single">
                                <label class="form-check-label" for="procedural_single">
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

        container.innerHTML = formHtml;
        this.initAppointmentForm('single');
    }

    addAnotherDoctorForm() {
        const multipleRadio = document.querySelector('input[name="appointment_chain_type"][value="multiple"]');
        if (multipleRadio) {
            multipleRadio.checked = true;
            this.onChainTypeChange('multiple');
        }
    }

    updateHiddenField() {
        const hiddenField = document.getElementById('id_additional_appointments_data');
        if (hiddenField) {
            const validAppointments = this.additionalAppointments.filter(app =>
                app.doctor_id && app.service_id && app.date && app.time_slot_id
            );
            hiddenField.value = JSON.stringify(validAppointments);
        }
    }

    updateProceduralHiddenField() {
        const hiddenField = document.getElementById('id_procedural_appointments_data');
        if (!hiddenField) {
            const newField = document.createElement('input');
            newField.type = 'hidden';
            newField.id = 'id_procedural_appointments_data';
            newField.name = 'procedural_appointments_data';

            const form = document.getElementById('appointmentForm');
            if (form) form.appendChild(newField);
            else return;
        }

        const field = document.getElementById('id_procedural_appointments_data');
        if (!field) return;

        const validData = this.proceduralAppointments.filter(item =>
            item.needs_procedural === true &&
            item.appointment_data &&
            item.appointment_data.doctor_id &&
            item.appointment_data.service_id &&
            item.appointment_data.date &&
            item.appointment_data.time_slot_id
        );

        field.value = JSON.stringify(validData);
    }

    async saveProceduralData(index, needsProcedural) {
        const formData = this.getFormData(index);
        if (!formData) return;

        const isValidForProcedural = formData.doctor_id &&
                                      formData.service_id &&
                                      formData.date &&
                                      formData.time_slot_id;

        if (!isValidForProcedural) {
            const existingIndex = this.proceduralAppointments.findIndex(item => item.index == index);
            if (existingIndex >= 0) this.proceduralAppointments.splice(existingIndex, 1);
            this.updateProceduralHiddenField();
            return;
        }

        if (needsProcedural) {
            const isProceduralAvailable = await this.checkProceduralAvailability(
                formData.date,
                formData.time_slot_id
            );

            if (!isProceduralAvailable) {
                const formElement = document.querySelector(`[data-form-index="${index}"]`);
                const proceduralCheckbox = formElement.querySelector('.procedural-checkbox');
                if (proceduralCheckbox) proceduralCheckbox.checked = false;
                alert('Процедурный кабинет в это время занят. Выберите другое время или отключите процедурный кабинет.');
                needsProcedural = false;
            }
        }

        const existingIndex = this.proceduralAppointments.findIndex(item => item.index == index);
        if (existingIndex >= 0) {
            this.proceduralAppointments[existingIndex] = {
                ...this.proceduralAppointments[existingIndex],
                needs_procedural: needsProcedural,
                appointment_data: formData
            };
        } else {
            this.proceduralAppointments.push({
                index: index,
                needs_procedural: needsProcedural,
                appointment_data: formData
            });
        }

        this.updateProceduralHiddenField();
    }

    async checkProceduralAvailability(date, timeSlotId) {
        try {
            const response = await fetch('/appointments/api/check-procedural-availability/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({ date: date, time_slot_id: timeSlotId })
            });

            if (!response.ok) {
                let errText = '';
                try {
                    const errData = await response.json();
                    errText = errData.error || JSON.stringify(errData);
                } catch (e) {
                    errText = `HTTP ${response.status}`;
                }
                console.warn('checkProceduralAvailability error:', { date, timeSlotId, status: response.status, errText });
                return false;
            }

            const data = await response.json();
            console.log('checkProceduralAvailability response:', { date, timeSlotId, data });
            return data.is_available === true;
        } catch (error) {
            console.error('checkProceduralAvailability fetch exception:', { date, timeSlotId, error });
            return false;
        }
    }

    validateTimeOverlap() {
        const mainAppointmentDate = this.mainDate;
        const mainTime = this.getMainAppointmentTime();

        if (!mainAppointmentDate || !mainTime) return { valid: true };

        const overlappingAppointments = [];
        this.additionalAppointments.forEach((appointment, index) => {
            if (appointment.date === mainAppointmentDate && appointment.time_slot_id) {
                overlappingAppointments.push({
                    index: index + 1,
                    date: appointment.date,
                    doctorId: appointment.doctor_id,
                    timeSlotId: appointment.time_slot_id
                });
            }
        });

        if (overlappingAppointments.length > 0) return { valid: true };
        return { valid: true };
    }

    validateBeforeSubmit() {
        const chainTypeElement = document.querySelector('input[name="appointment_chain_type"]:checked');
        if (!chainTypeElement) {
            alert('Пожалуйста, выберите тип записи');
            return false;
        }

        const chainType = chainTypeElement.value;
        this.updateHiddenField();
        this.updateProceduralHiddenField();

        // ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: если нет дополнительных записей, но выбран тип с ними
        if ((chainType === 'another_doctor' || chainType === 'multiple') &&
            this.additionalAppointments.length === 0) {
            alert('Для выбранного типа записи необходимо добавить хотя бы одну дополнительную запись');
            return false;
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
        const formElement = document.querySelector(`[data-form-index="${index}"]`);
        if (formElement) formElement.remove();

        const formIndex = this.appointmentForms.indexOf(index);
        if (formIndex > -1) this.appointmentForms.splice(formIndex, 1);

        const appointmentIndex = this.additionalAppointments.findIndex(app => app.index === index);
        if (appointmentIndex > -1) this.additionalAppointments.splice(appointmentIndex, 1);

        const proceduralIndex = this.proceduralAppointments.findIndex(item => item.index == index);
        if (proceduralIndex > -1) this.proceduralAppointments.splice(proceduralIndex, 1);

        const formData = this.getFormData(index);
        if (formData && formData.time_slot_id) this.bookedSlots.delete(formData.time_slot_id.toString());

        this.updateHiddenField();
        this.updateProceduralHiddenField();
    }

    getFormData(index) {
        let selector = index === 'single' ? '[data-form-index="single"]' : `[data-form-index="${index}"]`;
        const formElement = document.querySelector(selector);
        if (!formElement) return null;

        const doctorSelect = formElement.querySelector('.doctor-select');
        const serviceSelect = formElement.querySelector('.service-select');
        const dateInput = formElement.querySelector('.date-select');
        const slotSelect = formElement.querySelector('.slot-select');
        const commentInput = formElement.querySelector('.comment-input');
        const insuranceSelect = formElement.querySelector('.insurance-select');

        return {
            doctor_id: doctorSelect ? doctorSelect.value : null,
            service_id: serviceSelect ? serviceSelect.value : null,
            date: dateInput ? dateInput.value : null,
            time_slot_id: slotSelect ? slotSelect.value : null,
            comment: commentInput ? commentInput.value : null,
            insurance_type: insuranceSelect ? insuranceSelect.value : 'paid'
        };
    }

    setAllBookedSlots(slots) {
        if (slots && Array.isArray(slots)) {
            this.allBookedSlots = slots;
            slots.forEach(slot => {
                if (slot.id) this.bookedSlots.add(slot.id.toString());
            });
        }
    }

    // НОВЫЕ МЕТОДЫ ДЛЯ УПРАВЛЕНИЯ ФОРМАМИ
    removeSingleFormIfExists() {
        const singleForm = document.querySelector('[data-form-index="single"]');
        if (singleForm) {
            singleForm.remove();

            // Удаляем из массивов данных
            const singleIndex = this.additionalAppointments.findIndex(app => app.index === 'single');
            if (singleIndex > -1) {
                this.additionalAppointments.splice(singleIndex, 1);
            }

            const proceduralIndex = this.proceduralAppointments.findIndex(item => item.index == 'single');
            if (proceduralIndex > -1) {
                this.proceduralAppointments.splice(proceduralIndex, 1);
            }

            this.updateHiddenField();
            this.updateProceduralHiddenField();
        }
    }

    removeAllMultipleForms() {
        // Удаляем все формы с номерами
        document.querySelectorAll('[data-form-index]').forEach(formElement => {
            const index = formElement.getAttribute('data-form-index');
            if (index !== 'single' && index !== 'main') {
                formElement.remove();
            }
        });

        // Очищаем массивы
        this.appointmentForms = [];
        this.additionalAppointments = this.additionalAppointments.filter(app => app.index === 'single');
        this.proceduralAppointments = this.proceduralAppointments.filter(item => item.index == 'single');

        // Очищаем забронированные слоты (кроме основного)
        this.bookedSlots.clear();
        if (window.currentSlotId) {
            this.bookedSlots.add(window.currentSlotId.toString());
        }

        this.updateHiddenField();
        this.updateProceduralHiddenField();
    }

    // ИСПРАВЛЕННЫЙ МЕТОД ДЛЯ ПОЛУЧЕНИЯ УНИКАЛЬНЫХ ИМЕН ВРАЧЕЙ
    getUniqueAdditionalDoctorsNames() {
        const doctorNames = [];

        // Проверяем формы дополнительных записей
        this.appointmentForms.forEach(index => {
            const formElement = document.querySelector(`[data-form-index="${index}"]`);
            if (formElement) {
                const doctorSelect = formElement.querySelector('.doctor-select');
                if (doctorSelect && doctorSelect.value) {
                    const selectedOption = doctorSelect.options[doctorSelect.selectedIndex];
                    if (selectedOption) {
                        // Извлекаем только фамилию из текста
                        const text = selectedOption.textContent;
                        const surnameMatch = text.match(/^([А-ЯЁ][а-яё]+)/);
                        if (surnameMatch) {
                            const surname = surnameMatch[1];
                            // Добавляем только если еще нет
                            if (!doctorNames.includes(surname)) {
                                doctorNames.push(surname);
                            }
                        }
                    }
                }
            }
        });

        // Также проверяем форму "single" если есть
        const singleForm = document.querySelector('[data-form-index="single"]');
        if (singleForm) {
            const doctorSelect = singleForm.querySelector('.doctor-select');
            if (doctorSelect && doctorSelect.value) {
                const selectedOption = doctorSelect.options[doctorSelect.selectedIndex];
                if (selectedOption) {
                    const text = selectedOption.textContent;
                    const surnameMatch = text.match(/^([А-ЯЁ][а-яё]+)/);
                    if (surnameMatch) {
                        const surname = surnameMatch[1];
                        // Добавляем только если еще нет
                        if (!doctorNames.includes(surname)) {
                            doctorNames.push(surname);
                        }
                    }
                }
            }
        }

        return doctorNames;
    }
}

// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
function extractSurname(fullName) {
    if (!fullName) return '';
    const surnameMatch = fullName.match(/^([А-ЯЁ][а-яё]+)/);
    return surnameMatch ? surnameMatch[1] : fullName;
}

function getDoctorName() {
    // 1. Из скрытого поля с полным именем
    const hiddenDoctorName = document.getElementById('js-doctor-name');
    if (hiddenDoctorName && hiddenDoctorName.value) {
        return hiddenDoctorName.value;
    }

    // 2. Из скрытого поля с фамилией
    const hiddenDoctorSurname = document.getElementById('js-main-doctor-name');
    if (hiddenDoctorSurname && hiddenDoctorSurname.value) {
        return hiddenDoctorSurname.value;
    }

    // 3. Из глобальной переменной
    if (typeof doctorName !== 'undefined' && doctorName) {
        return doctorName;
    }

    // 4. Из элемента на странице
    const doctorNameSpan = document.getElementById('doctor-full-name');
    if (doctorNameSpan && doctorNameSpan.textContent) {
        return doctorNameSpan.textContent.trim();
    }

    // 5. Из заголовка
    const header = document.querySelector('.card-title');
    if (header) {
        return header.textContent.trim();
    }

    console.error('Could not determine doctor name');
    return '';
}

AppointmentChainManager.prototype.bindFormEvents = function(index) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) return;

    const doctorSelect = formElement.querySelector('.doctor-select');
    doctorSelect.addEventListener('change', (e) => this.onDoctorSelect(index, e.target.value));

    const dateInput = formElement.querySelector('.date-select');
    dateInput.addEventListener('change', (e) => this.onDateSelect(index, e.target.value));

    const slotSelect = formElement.querySelector('.slot-select');
    slotSelect.addEventListener('change', (e) => this.onSlotSelect(index, e.target.value));

    const removeBtn = formElement.querySelector('.remove-form');
    if (removeBtn) removeBtn.addEventListener('click', () => this.removeAppointmentForm(index));

    const commentInput = formElement.querySelector('.comment-input');
    commentInput.addEventListener('input', (e) => this.onCommentChange(index, e.target.value));

    const serviceSelect = formElement.querySelector('.service-select');
    if (serviceSelect) {
        serviceSelect.addEventListener('change', (e) => {
            this.onServiceSelect(index, e.target.value);
            this.saveFormData(index);
        });
    }

    const proceduralCheckbox = formElement.querySelector('.procedural-checkbox');
    if (proceduralCheckbox) {
        proceduralCheckbox.addEventListener('change', (e) => {
            this.saveProceduralData(index, e.target.checked);
        });

        if (proceduralCheckbox.checked) this.saveProceduralData(index, true);
    }
    const insuranceSelect = formElement.querySelector('.insurance-select');
    if (insuranceSelect) {
        insuranceSelect.addEventListener('change', (e) => this.saveFormData(index));
    }
};

AppointmentChainManager.prototype.onDoctorSelect = async function(index, doctorId) {
    if (!doctorId) return;

    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) return;

    const doctorNameSpan = formElement.querySelector('.doctor-name');

    try {
        const dateInput = formElement.querySelector('.date-select');
        const selectedDate = dateInput ? dateInput.value : null;

        const data = await this.fetchDoctorServices({
            doctorId: doctorId,
            date: selectedDate || null
        });
        if (data.success) {
            if (doctorNameSpan && data.doctor) doctorNameSpan.textContent = data.doctor.name;

            serviceSelect.innerHTML = '<option value="">Выберите услугу...</option>';
            data.services.forEach(service => {
                const option = document.createElement('option');
                option.value = service.id;
                option.textContent = `${service.name} (${service.price} руб.)`;
                option.dataset.price = service.price;
                serviceSelect.appendChild(option);
            });

            serviceSelect.disabled = false;

            const dateInput = formElement.querySelector('.date-select');
            if (dateInput && dateInput.value) this.onDateSelect(index, dateInput.value);
        }
    } catch (error) {}
};

AppointmentChainManager.prototype.fetchDoctorServices = async function({doctorId, date = null, timeSlotId = null}) {
    const response = await fetch('/appointments/api/doctor-services/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken
        },
        body: JSON.stringify({
            doctor_id: doctorId,
            date: date,
            time_slot_id: timeSlotId
        })
    });

    return response.json();
};

AppointmentChainManager.prototype.replaceServiceOptions = function(serviceSelect, services, selectedValue = '') {
    if (!serviceSelect) return;

    serviceSelect.innerHTML = '<option value="">Выберите услугу...</option>';
    services.forEach(service => {
        const option = document.createElement('option');
        option.value = service.id;
        option.textContent = `${service.name} (${service.price} СЂСѓР±.)`;
        option.dataset.price = service.price;
        serviceSelect.appendChild(option);
    });

    const hasSelectedValue = selectedValue && services.some(service => String(service.id) === String(selectedValue));
    serviceSelect.value = hasSelectedValue ? selectedValue : '';
    serviceSelect.disabled = false;
    serviceSelect.dispatchEvent(new Event('change'));
};

AppointmentChainManager.prototype.refreshServicesForForm = async function(index, {doctorId, date = null, timeSlotId = null}) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) return;

    const serviceSelect = formElement.querySelector('.service-select');
    if (!serviceSelect || !doctorId) return;

    try {
        const currentServiceValue = serviceSelect.value;
        const servicesData = await this.fetchDoctorServices({
            doctorId: doctorId,
            date: date,
            timeSlotId: timeSlotId
        });

        if (servicesData.success && servicesData.services) {
            this.replaceServiceOptions(serviceSelect, servicesData.services, currentServiceValue);
        }
    } catch (error) {}
};

AppointmentChainManager.prototype.refreshServicesForSelectedSlot = async function(index, slotId) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) return;

    const doctorSelect = formElement.querySelector('.doctor-select');
    const dateInput = formElement.querySelector('.date-select');

    if (!doctorSelect || !doctorSelect.value) return;

    await this.refreshServicesForForm(index, {
        doctorId: doctorSelect.value,
        date: dateInput ? dateInput.value : null,
        timeSlotId: slotId || null
    });
};

AppointmentChainManager.prototype.onDateSelect = async function(index, date) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) return;

    this.clearTimeOverlapError(index);

    const doctorSelect = formElement.querySelector('.doctor-select');
    const slotSelect = formElement.querySelector('.slot-select');
    const dateSpan = formElement.querySelector('.appointment-date');

    const doctorId = doctorSelect.value;
    if (!doctorId || !date) return;

    const mainTime = this.getMainAppointmentTime();
    const isSameDate = date === window.originalDate;

    if (dateSpan) dateSpan.textContent = date;
        // Обновим цены услуг на выбранную дату (не меняя выбранную услугу)
    try {
        const serviceSelect = formElement.querySelector('.service-select');
        if (serviceSelect) {
            const currentServiceValue = serviceSelect.value;

            const respServices = await fetch('/appointments/api/doctor-services/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({ doctor_id: doctorId, date: date })
            });

            const servicesData = await respServices.json();
            if (servicesData.success && servicesData.services) {
                const map = new Map();
                servicesData.services.forEach(s => map.set(String(s.id), s));

                Array.from(serviceSelect.options).forEach(opt => {
                    if (!opt.value) return;
                    const s = map.get(String(opt.value));
                    if (!s) return;
                    opt.textContent = `${s.name} (${s.price} руб.)`;
                    opt.dataset.price = s.price;
                });

                serviceSelect.value = currentServiceValue;
                serviceSelect.dispatchEvent(new Event('change'));
            }
        }
    } catch (e) {}

    try {
        const requestData = {
            doctor_id: doctorId,
            date: date,
            booked_slots: Array.from(this.bookedSlots),
            main_appointment_time: isSameDate ? mainTime : null,
            main_appointment_date: window.originalDate
        };

        const response = await fetch('/appointments/api/available-slots-for-doctor/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify(requestData)
        });

        const data = await response.json();
        if (data.success && data.slots) {
            slotSelect.innerHTML = '';

            const oldError = formElement.querySelector('.slot-error');
            if (oldError) oldError.remove();
            slotSelect.classList.remove('is-invalid');
            this.clearTimeOverlapError(index);

            let availableSlotsCount = 0;

            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = 'Выберите время...';
            slotSelect.appendChild(defaultOption);

            data.slots.forEach(slot => {
                const option = document.createElement('option');
                option.value = slot.id;
                option.textContent = `${slot.time} (${slot.cabinet})`;
                option.dataset.startTime = slot.start_time;
                option.dataset.endTime = slot.end_time;
                option.dataset.time = `${slot.time} (${slot.cabinet})`;
                option.dataset.cabinet = slot.cabinet;
                slotSelect.appendChild(option);
                availableSlotsCount++;
            });

            slotSelect.disabled = availableSlotsCount === 0;

            if (availableSlotsCount === 0) {
                if (isSameDate && mainTime) {
                    const noSlotsOption = document.createElement('option');
                    noSlotsOption.value = '';
                    noSlotsOption.textContent = 'Нет доступных слотов (время пересекается с основной записью)';
                    slotSelect.appendChild(noSlotsOption);
                    this.showNoAvailableSlotsMessage(formElement, mainTime);
                } else {
                    const noSlotsOption = document.createElement('option');
                    noSlotsOption.value = '';
                    noSlotsOption.textContent = 'Нет доступных слотов';
                    slotSelect.appendChild(noSlotsOption);
                }
            }
        } else {
            slotSelect.innerHTML = '<option value="">Ошибка загрузки слотов</option>';
            slotSelect.disabled = true;
        }
    } catch (error) {
        slotSelect.innerHTML = '<option value="">Ошибка загрузки слотов</option>';
        slotSelect.disabled = true;
    }
};

AppointmentChainManager.prototype.showNoAvailableSlotsMessage = function(formElement, mainTime) {
    const oldMessage = formElement.querySelector('.no-available-slots-message');
    if (oldMessage) oldMessage.remove();

    const slotSelect = formElement.querySelector('.slot-select');
    if (!slotSelect) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = 'no-available-slots-message alert alert-warning mt-2';
    messageDiv.innerHTML = `
        <div class="d-flex align-items-start">
            <i class="fas fa-info-circle me-2 mt-1"></i>
            <div>
                <strong>Нет доступных временных слотов</strong><br>
                Все временные слоты на эту дату пересекаются с основной записью:<br>
                • Основная запись: ${mainTime.time}<br>
                <small class="text-muted">
                    Пожалуйста, выберите другую дату для этой записи или другое время для основной записи.
                </small>
            </div>
        </div>
    `;

    slotSelect.parentNode.appendChild(messageDiv);
};

AppointmentChainManager.prototype.onSlotSelect = function(index, slotId) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    const slotSelect = formElement.querySelector('.slot-select');
    const timeSpan = formElement.querySelector('.appointment-time');

    if (!slotId) {
        if (timeSpan) timeSpan.textContent = 'не выбрано';

        const formData = this.getFormData(index);
        if (formData && formData.time_slot_id) this.bookedSlots.delete(formData.time_slot_id.toString());

        this.saveFormData(index);
        return;
    }

    const selectedOption = slotSelect.options[slotSelect.selectedIndex];
    if (!selectedOption) return;

    // ПРОВЕРКА ДЛЯ ПИЩЕЛЕВА
    if (window.AppointmentUtils && window.AppointmentUtils.PishchelevValidator) {
        const doctorSelect = formElement.querySelector('.doctor-select');
        const serviceSelect = formElement.querySelector('.service-select');

        if (doctorSelect && serviceSelect) {
            const doctorName = doctorSelect.options[doctorSelect.selectedIndex]?.textContent || '';
            const serviceName = serviceSelect.options[serviceSelect.selectedIndex]?.textContent || '';

            if (window.AppointmentUtils.PishchelevValidator.isPishchelevDoctor(doctorName) && serviceName) {
                const timeText = selectedOption.dataset.time || '';
                const slotDuration = window.AppointmentUtils.PishchelevValidator.getSlotDuration(timeText);

                if (slotDuration !== null) {
                    const validation = window.AppointmentUtils.PishchelevValidator.validateSlotForPishchelev(
                        slotDuration, serviceName, doctorName
                    );

                    if (!validation.valid) {
                        this.showPishchelevTimeError(formElement, validation.message, selectedOption);
                        slotSelect.value = '';
                        if (timeSpan) timeSpan.textContent = 'не выбрано';
                        slotSelect.classList.add('is-invalid');
                        return;
                    }
                }
            }
        }
    }

    if (this.shouldCheckTimeOverlap()) {
        const dateInput = formElement.querySelector('.date-select');
        const slotDate = dateInput ? dateInput.value : null;

        if (slotDate === window.originalDate && selectedOption.dataset.startTime && selectedOption.dataset.endTime) {
            const isOverlapping = this.checkSlotTimeOverlap(
                selectedOption.dataset.startTime,
                selectedOption.dataset.endTime
            );

            if (isOverlapping) {
                this.showTimeOverlapWarning(index, selectedOption);
                slotSelect.value = '';
                if (timeSpan) timeSpan.textContent = 'не выбрано';
                slotSelect.classList.add('is-invalid');
                return;
            }
        }
    }

    if (selectedOption.dataset.time && timeSpan) timeSpan.textContent = selectedOption.dataset.time;

    this.bookedSlots.add(slotId.toString());
    slotSelect.classList.remove('is-invalid');
    this.clearTimeOverlapError(index);

    const noSlotsMessage = formElement.querySelector('.no-available-slots-message');
    if (noSlotsMessage) noSlotsMessage.remove();

    this.saveFormData(index);
};

AppointmentChainManager.prototype.showPishchelevTimeError = function(formElement, message, slotOption) {
    const slotSelect = formElement.querySelector('.slot-select');

    const oldError = formElement.querySelector('.pishchelev-time-error');
    if (oldError) oldError.remove();

    const errorDiv = document.createElement('div');
    errorDiv.className = 'pishchelev-time-error invalid-feedback d-block';
    errorDiv.innerHTML = `
        <div class="alert alert-danger alert-dismissible fade show mt-2" role="alert">
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>Ошибка записи к врачу Пищелеву!</strong><br>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;

    slotSelect.parentNode.appendChild(errorDiv);

    alert(message + '\n\nВыбранное время: ' + slotOption.dataset.time);
};

AppointmentChainManager.prototype.clearTimeOverlapError = function(index) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) return;

    const overlapError = formElement.querySelector('.slot-time-overlap-error');
    if (overlapError) overlapError.remove();

    const noSlotsMessage = formElement.querySelector('.no-available-slots-message');
    if (noSlotsMessage) noSlotsMessage.remove();

    const slotSelect = formElement.querySelector('.slot-select');
    if (slotSelect) slotSelect.classList.remove('is-invalid');
};

AppointmentChainManager.prototype.shouldCheckTimeOverlap = function() {
    return window.originalDate && this.getMainAppointmentTime();
};

AppointmentChainManager.prototype.showTimeOverlapWarning = function(index, slotOption) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    const slotSelect = formElement.querySelector('.slot-select');

    const oldError = formElement.querySelector('.slot-time-overlap-error');
    if (oldError) oldError.remove();

    const errorDiv = document.createElement('div');
    errorDiv.className = 'slot-time-overlap-error invalid-feedback d-block';
    errorDiv.innerHTML = `
        <div class="alert alert-danger alert-dismissible fade show mt-2" role="alert">
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>Ошибка: время пересекается с основной записью!</strong><br>
            Основная запись: ${window.originalDate} ${this.getMainAppointmentTime().time}<br>
            Выбранное время: ${slotOption.dataset.time}<br>
            <small>Пожалуйста, выберите другое время, которое не пересекается с основной записью.</small>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;

    slotSelect.parentNode.appendChild(errorDiv);

    alert(
        '❌ Вы не можете выбрать это время!\n\n' +
        'Причина: время пересекается с основной записью.\n\n' +
        'Основная запись: ' + window.originalDate + ' ' + this.getMainAppointmentTime().time + '\n' +
        'Выбранное время: ' + slotOption.dataset.time + '\n\n' +
        'Пожалуйста, выберите другое время, которое не пересекается с основной записью.'
    );
};

AppointmentChainManager.prototype.onServiceSelect = function(index, serviceId) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) return;

    const doctorSelect = formElement.querySelector('.doctor-select');
    const serviceSelect = formElement.querySelector('.service-select');
    const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];

    if (!selectedOption || !doctorSelect) return;

    const doctorName = doctorSelect.options[doctorSelect.selectedIndex]?.textContent || '';
    const serviceName = selectedOption.textContent;

    // Проверяем для Пищелева
    if (window.AppointmentUtils && window.AppointmentUtils.PishchelevValidator) {
        const slotSelect = formElement.querySelector('.slot-select');
        const timeText = slotSelect?.options[slotSelect.selectedIndex]?.dataset.time || '';

        const validation = window.AppointmentUtils.PishchelevValidator.validateChainForPishchelev(
            formElement, index
        );

        if (!validation.valid) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'pishchelev-service-error invalid-feedback d-block';
            errorDiv.innerHTML = `
                <div class="alert alert-danger alert-dismissible fade show mt-2" role="alert">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    <strong>Ошибка записи к врачу Пищелеву!</strong><br>
                    ${validation.message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;

            const oldError = formElement.querySelector('.pishchelev-service-error');
            if (oldError) oldError.remove();

            serviceSelect.parentNode.appendChild(errorDiv);
            serviceSelect.classList.add('is-invalid');
            if (slotSelect) slotSelect.classList.add('is-invalid');

            alert(validation.message);
            serviceSelect.value = '';
            if (slotSelect) slotSelect.value = '';

            return;
        } else {
            const error = formElement.querySelector('.pishchelev-service-error');
            if (error) error.remove();
            serviceSelect.classList.remove('is-invalid');
            if (slotSelect) slotSelect.classList.remove('is-invalid');
        }
    }

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
    const insuranceSelect = formElement.querySelector('.insurance-select');
    const proceduralCheckbox = formElement.querySelector('.procedural-checkbox');

    const appointmentData = {
        doctor_id: doctorSelect ? doctorSelect.value : null,
        service_id: serviceSelect ? serviceSelect.value : null,
        date: dateInput ? dateInput.value : null,
        time_slot_id: slotSelect ? slotSelect.value : null,
        comment: commentInput ? commentInput.value : null,
        insurance_type: insuranceSelect ? insuranceSelect.value : 'paid'
    };



    const isValid = appointmentData.doctor_id &&
                   appointmentData.service_id &&
                   appointmentData.date &&
                   appointmentData.time_slot_id;

    const existingIndex = this.additionalAppointments.findIndex(app => app.index === index);

    if (isValid) {
        if (existingIndex >= 0) {
            this.additionalAppointments[existingIndex] = { index: index, ...appointmentData };
        } else {
            this.additionalAppointments.push({ index: index, ...appointmentData });
        }

        formElement.classList.remove('border-danger');

        if (proceduralCheckbox && proceduralCheckbox.checked) this.saveProceduralData(index, true);
    } else {
        if (existingIndex >= 0) this.additionalAppointments.splice(existingIndex, 1);
        formElement.classList.add('border-danger');

        const proceduralIndex = this.proceduralAppointments.findIndex(item => item.index == index);
        if (proceduralIndex >= 0) {
            this.proceduralAppointments.splice(proceduralIndex, 1);
            this.updateProceduralHiddenField();
        }

        if (appointmentData.time_slot_id) this.bookedSlots.delete(appointmentData.time_slot_id.toString());
    }

    this.updateHiddenField();
    this.updateProceduralHiddenField();
};

AppointmentChainManager.prototype.onCommentChange = function(index, comment) {
    this.saveFormData(index);
};

AppointmentChainManager.prototype.replaceServiceOptions = function(serviceSelect, services, selectedValue = '') {
    if (!serviceSelect) return;

    serviceSelect.innerHTML = '<option value="">Выберите услугу...</option>';
    services.forEach(service => {
        const option = document.createElement('option');
        option.value = service.id;
        option.textContent = `${service.name} (${service.price} руб.)`;
        option.dataset.price = service.price;
        serviceSelect.appendChild(option);
    });

    const hasSelectedValue = selectedValue && services.some(service => String(service.id) === String(selectedValue));
    serviceSelect.value = hasSelectedValue ? selectedValue : '';
    serviceSelect.disabled = false;
    serviceSelect.dispatchEvent(new Event('change'));
};

AppointmentChainManager.prototype.onDoctorSelect = async function(index, doctorId) {
    if (!doctorId) return;

    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    if (!formElement) return;

    const doctorNameSpan = formElement.querySelector('.doctor-name');

    try {
        const dateInput = formElement.querySelector('.date-select');
        const selectedDate = dateInput ? dateInput.value : null;
        const data = await this.fetchDoctorServices({
            doctorId: doctorId,
            date: selectedDate || null
        });

        if (data.success) {
            if (doctorNameSpan && data.doctor) doctorNameSpan.textContent = data.doctor.name;

            this.replaceServiceOptions(formElement.querySelector('.service-select'), data.services);

            if (dateInput && dateInput.value) this.onDateSelect(index, dateInput.value);
        }
    } catch (error) {}
};

AppointmentChainManager.prototype.onSlotSelect = function(index, slotId) {
    const formElement = document.querySelector(`[data-form-index="${index}"]`);
    const slotSelect = formElement.querySelector('.slot-select');
    const timeSpan = formElement.querySelector('.appointment-time');

    if (!slotId) {
        if (timeSpan) timeSpan.textContent = '\u043d\u0435 \u0432\u044b\u0431\u0440\u0430\u043d\u043e';

        const formData = this.getFormData(index);
        if (formData && formData.time_slot_id) this.bookedSlots.delete(formData.time_slot_id.toString());

        this.saveFormData(index);
        this.refreshServicesForSelectedSlot(index, null);
        return;
    }

    const selectedOption = slotSelect.options[slotSelect.selectedIndex];
    if (!selectedOption) return;

    if (window.AppointmentUtils && window.AppointmentUtils.PishchelevValidator) {
        const doctorSelect = formElement.querySelector('.doctor-select');
        const serviceSelect = formElement.querySelector('.service-select');

        if (doctorSelect && serviceSelect) {
            const doctorName = doctorSelect.options[doctorSelect.selectedIndex]?.textContent || '';
            const serviceName = serviceSelect.options[serviceSelect.selectedIndex]?.textContent || '';

            if (window.AppointmentUtils.PishchelevValidator.isPishchelevDoctor(doctorName) && serviceName) {
                const timeText = selectedOption.dataset.time || '';
                const slotDuration = window.AppointmentUtils.PishchelevValidator.getSlotDuration(timeText);

                if (slotDuration !== null) {
                    const validation = window.AppointmentUtils.PishchelevValidator.validateSlotForPishchelev(
                        slotDuration, serviceName, doctorName
                    );

                    if (!validation.valid) {
                        this.showPishchelevTimeError(formElement, validation.message, selectedOption);
                        slotSelect.value = '';
                        if (timeSpan) timeSpan.textContent = '\u043d\u0435 \u0432\u044b\u0431\u0440\u0430\u043d\u043e';
                        slotSelect.classList.add('is-invalid');
                        return;
                    }
                }
            }
        }
    }

    if (this.shouldCheckTimeOverlap()) {
        const dateInput = formElement.querySelector('.date-select');
        const slotDate = dateInput ? dateInput.value : null;

        if (slotDate === window.originalDate && selectedOption.dataset.startTime && selectedOption.dataset.endTime) {
            const isOverlapping = this.checkSlotTimeOverlap(
                selectedOption.dataset.startTime,
                selectedOption.dataset.endTime
            );

            if (isOverlapping) {
                this.showTimeOverlapWarning(index, selectedOption);
                slotSelect.value = '';
                if (timeSpan) timeSpan.textContent = '\u043d\u0435 \u0432\u044b\u0431\u0440\u0430\u043d\u043e';
                slotSelect.classList.add('is-invalid');
                return;
            }
        }
    }

    if (selectedOption.dataset.time && timeSpan) timeSpan.textContent = selectedOption.dataset.time;

    this.bookedSlots.add(slotId.toString());
    slotSelect.classList.remove('is-invalid');
    this.clearTimeOverlapError(index);

    const noSlotsMessage = formElement.querySelector('.no-available-slots-message');
    if (noSlotsMessage) noSlotsMessage.remove();

    this.saveFormData(index);
    this.refreshServicesForSelectedSlot(index, slotId);
};

window.AppointmentChainManager = AppointmentChainManager;
