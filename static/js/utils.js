/**
 * Общие утилиты для работы с формами записи
 */
(function() {
    'use strict';

    // Защита от повторной инициализации
    if (window.AppointmentUtils) {
        console.warn('AppointmentUtils уже инициализирован');
        return;
    }

    // Основной объект утилит
    window.AppointmentUtils = {
        // ==================== ФОРМАТИРОВАНИЕ ТЕЛЕФОНА ====================
        PhoneFormatter: {
            format: function(input) {
                if (!input) return;

                let value = input.value.replace(/[^\d+]/g, '');

                if (!value.startsWith('+7') && value.length > 0) {
                    if (value.startsWith('7') || value.startsWith('8')) {
                        value = '+7' + value.slice(1);
                    } else {
                        value = '+7' + value;
                    }
                }

                if (value.length > 12) {
                    value = value.substring(0, 12);
                }

                input.value = value;
            },

            initialize: function(phoneInput) {
                if (!phoneInput) return;

                phoneInput.addEventListener('input', function() {
                    window.AppointmentUtils.PhoneFormatter.format(this);
                });

                phoneInput.addEventListener('blur', function() {
                    window.AppointmentUtils.PhoneFormatter.format(this);
                });

                if (phoneInput.value) {
                    window.AppointmentUtils.PhoneFormatter.format(phoneInput);
                }
            }
        },

        // ==================== ВАЛИДАЦИЯ УСЛУГ ====================
        ServiceValidator: {
            isMedicalBlockade: function(serviceSelect) {
                if (!serviceSelect) return false;

                const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
                if (!selectedOption || selectedOption.value === '') {
                    return false;
                }

                const serviceName = selectedOption.text.toLowerCase();
                const blockadeKeywords = ['блокад', 'введение', 'инъекц', 'укол', 'инфузи'];

                return blockadeKeywords.some(keyword => serviceName.includes(keyword));
            },

            isInsolesService: function(serviceName) {
                if (!serviceName) return false;

                const serviceNameLower = serviceName.toLowerCase();
                const insolesKeywords = ["стель", "стелек", "manufacture_of_insoles"];

                return insolesKeywords.some(keyword => serviceNameLower.includes(keyword));
            },

            getSlotDurationFromText: function(timeText) {
                const timeMatch = timeText.match(/(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})/);
                if (timeMatch) {
                    const startHours = parseInt(timeMatch[1]);
                    const startMinutes = parseInt(timeMatch[2]);
                    const endHours = parseInt(timeMatch[3]);
                    const endMinutes = parseInt(timeMatch[4]);

                    return (endHours * 60 + endMinutes) - (startHours * 60 + startMinutes);
                }
                return null;
            },

            checkPishchelevRestrictions: function(doctorName, serviceName, slotDuration) {
                const isPishchelev = doctorName.includes('Пищелёв');
                const isInsolesServiceValue = window.AppointmentUtils.ServiceValidator.isInsolesService(serviceName);

                if (isPishchelev && slotDuration === 20 && !isInsolesServiceValue) {
                    return {
                        allowed: false,
                        message: 'Врач Пищелев П.В. на 20-минутные интервалы принимает ТОЛЬКО на изготовление стелек. Выберите услугу "Изготовление стелек" или 30-минутный интервал.'
                    };
                }

                return { allowed: true };
            },

            checkServiceRestrictions: function(serviceSelect) {
                if (!serviceSelect) return;

                const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
                if (!selectedOption) return;

                const serviceName = selectedOption.textContent;
                const doctorName = document.querySelector('.card-title')?.textContent || '';
                const timeText = document.querySelector('.alert-info')?.textContent || '';

                const slotDuration = window.AppointmentUtils.ServiceValidator.getSlotDurationFromText(timeText);
                if (slotDuration !== null) {
                    const restriction = window.AppointmentUtils.ServiceValidator.checkPishchelevRestrictions(
                        doctorName,
                        serviceName,
                        slotDuration
                    );
                    if (!restriction.allowed) {
                        alert(restriction.message);
                    }
                }
            }
        },

        // ==================== ПРОВЕРКА ПАЦИЕНТА ====================
        PatientChecker: {
            create: function(options) {
                return {
                    checkPatientUrl: options.checkPatientUrl,
                    csrfToken: options.csrfToken,

                    checkPatient: async function(patientData) {
                        try {
                            const response = await fetch(this.checkPatientUrl, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': this.csrfToken
                                },
                                body: JSON.stringify(patientData)
                            });

                            if (!response.ok) {
                                throw new Error(`HTTP error! status: ${response.status}`);
                            }

                            return await response.json();
                        } catch (error) {
                            console.error('Error checking patient:', error);
                            throw error;
                        }
                    },

                    createResultHtml: function(data) {
                        if (data.error) {
                            return `<div class="alert alert-danger">${data.error}</div>`;
                        }

                        if (data.exists) {
                            const patient = data.patient;
                            let message = `<div class="alert alert-warning">
                                <i class="fas fa-exclamation-triangle"></i>
                                <strong>Пациент уже существует в базе!</strong><br>`;

                            message += `<strong>ФИО:</strong> ${patient.full_name}<br>`;

                            if (patient.card_number) {
                                message += `<strong>Номер карты:</strong> ${patient.card_number}<br>`;
                            } else {
                                message += `<strong>Номер карты:</strong> не указан<br>`;
                            }

                            if (patient.phone_number) {
                                message += `<strong>Телефон:</strong> ${patient.phone_number}<br>`;
                            }

                            message += `<small class="text-muted">Система автоматически использует существующую запись при сохранении</small>`;
                            message += `</div>`;

                            return message;
                        } else {
                            return `<div class="alert alert-success">
                                <i class="fas fa-check-circle"></i>
                                <strong>Пациент не найден в базе.</strong><br>
                                Будет создана новая запись пациента.
                            </div>`;
                        }
                    },

                    autoFillForm: function(patient) {
                        const fields = {
                            'id_surname': 'surname',
                            'id_first_name': 'first_name',
                            'id_last_name': 'last_name',
                            'id_phone_number': 'phone_number',
                            'id_card_number': 'card_number'
                        };

                        Object.entries(fields).forEach(([fieldId, patientField]) => {
                            const field = document.getElementById(fieldId);
                            if (field && patient[patientField]) {
                                field.value = patient[patientField];
                            }
                        });

                        // Особый случай для даты рождения
                        if (patient.date_of_birth) {
                            const dobField = document.getElementById('id_date_of_birth');
                            if (dobField) {
                                const dob = new Date(patient.date_of_birth);
                                const formattedDob = dob.toISOString().split('T')[0];
                                dobField.value = formattedDob;
                            }
                        }
                    },

                    initializeCheckButton: function(buttonId, resultContainerId) {
                        const button = document.getElementById(buttonId);
                        const resultContainer = document.getElementById(resultContainerId);

                        if (!button || !resultContainer) {
                            console.error('Patient check elements not found:', { buttonId, resultContainerId });
                            return;
                        }

                        const self = this; // Сохраняем контекст

                        button.addEventListener('click', async function() {
                            const surname = document.getElementById('id_surname')?.value.trim();
                            const firstName = document.getElementById('id_first_name')?.value.trim();
                            const dateOfBirth = document.getElementById('id_date_of_birth')?.value;

                            if (!surname || !firstName) {
                                resultContainer.innerHTML = '<div class="alert alert-warning">Заполните фамилию и имя для проверки</div>';
                                resultContainer.style.display = 'block';
                                return;
                            }

                            const originalText = button.innerHTML;
                            button.disabled = true;
                            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Проверяем...';

                            resultContainer.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> Проверяем пациента в базе данных...</div>';
                            resultContainer.style.display = 'block';

                            const requestData = { surname, first_name: firstName };
                            if (dateOfBirth) requestData.date_of_birth = dateOfBirth;

                            try {
                                const data = await self.checkPatient(requestData);

                                if (data.exists && data.patient) {
                                    self.autoFillForm(data.patient);
                                }

                                resultContainer.innerHTML = self.createResultHtml(data);
                            } catch (error) {
                                resultContainer.innerHTML = `<div class="alert alert-danger">Ошибка при проверке пациента: ${error.message}</div>`;
                            } finally {
                                button.disabled = false;
                                button.innerHTML = originalText;
                            }
                        });
                    }
                };
            }
        },

        // ==================== МЕНЕДЖЕР ТИПОВ ЗАПИСЕЙ ====================
        AppointmentTypeManager: {
            create: function(options) {
                const manager = {
                    radios: options.radios || document.querySelectorAll('input[name="appointment_type"]'),
                    additionalServiceSection: options.additionalServiceSection,
                    twoSlotsSection: options.twoSlotsSection,
                    additionalServiceSelect: options.additionalServiceSelect,
                    mainServiceSelect: options.mainServiceSelect,

                    initialize: function() {
                        if (this.radios.length > 0) {
                            this.radios.forEach(radio => {
                                radio.addEventListener('change', (event) => this.handleTypeChange(event));
                            });

                            // Триггерим изменение для выбранного радио
                            const checkedRadio = document.querySelector('input[name="appointment_type"]:checked');
                            if (checkedRadio) {
                                checkedRadio.dispatchEvent(new Event('change'));
                            }
                        } else {
                            console.warn('No appointment type radios found');
                        }

                        // Обновляем дополнительные услуги при изменении основной
                        if (this.mainServiceSelect && this.additionalServiceSelect) {
                            this.mainServiceSelect.addEventListener('change', () => {
                                if (this.additionalServiceSection &&
                                    this.additionalServiceSection.style.display === 'block') {
                                    this.populateAdditionalServices();
                                }
                            });
                        }
                    },

                    handleTypeChange: function(event) {
                        const value = event.target.value;

                        // Скрываем все секции
                        if (this.additionalServiceSection) {
                            this.additionalServiceSection.style.display = 'none';
                        }
                        if (this.twoSlotsSection) {
                            this.twoSlotsSection.style.display = 'none';
                        }

                        // Показываем нужную секцию
                        switch (value) {
                            case 'additional':
                                if (this.additionalServiceSection) {
                                    this.additionalServiceSection.style.display = 'block';
                                    this.populateAdditionalServices();
                                }
                                break;
                            case 'two_slots':
                                if (this.twoSlotsSection) {
                                    this.twoSlotsSection.style.display = 'block';
                                }
                                break;
                        }
                    },

                    populateAdditionalServices: function() {
                        if (!this.additionalServiceSelect || !this.mainServiceSelect) return;

                        this.additionalServiceSelect.innerHTML = '<option value="">---------</option>';

                        const mainOptions = this.mainServiceSelect.querySelectorAll('option');
                        mainOptions.forEach(option => {
                            if (option.value !== '') {
                                const newOption = document.createElement('option');
                                newOption.value = option.value;
                                newOption.textContent = option.textContent;
                                this.additionalServiceSelect.appendChild(newOption);
                            }
                        });
                    }
                };

                manager.initialize();
                return manager;
            }
        },

        // ==================== ОБНОВЛЕНИЕ СУММЫ ====================
        TotalSumUpdater: {
            updateTotalSum: function() {
                const serviceSelect = document.getElementById('id_service');
                const totalField = document.getElementById('id_total_sum');

                if (!serviceSelect || !totalField) return;

                const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
                if (selectedOption && selectedOption.dataset.price) {
                    totalField.value = parseFloat(selectedOption.dataset.price).toFixed(2);
                } else if (selectedOption) {
                    // Пытаемся извлечь цену из текста опции
                    const priceMatch = selectedOption.text.match(/\((\d+(?:\.\d{2})?) руб\.\)/);
                    if (priceMatch && priceMatch[1]) {
                        totalField.value = parseFloat(priceMatch[1]).toFixed(2);
                    }
                }
            },

            initialize: function(serviceSelectId, totalFieldId) {
                const serviceSelect = document.getElementById(serviceSelectId);
                const totalField = document.getElementById(totalFieldId);
                const form = document.getElementById('appointmentForm');

                if (!serviceSelect || !totalField) return;

                // Обновляем при изменении услуги
                serviceSelect.addEventListener('change', window.AppointmentUtils.TotalSumUpdater.updateTotalSum);

                // Инициализируем при загрузке
                window.AppointmentUtils.TotalSumUpdater.updateTotalSum();

                // Обновляем перед отправкой формы
                if (form) {
                    form.addEventListener('submit', function() {
                        window.AppointmentUtils.TotalSumUpdater.updateTotalSum();
                    });
                }
            }
        },

        // ==================== УТИЛИТА ДЛЯ РАБОТЫ СО СЛОТАМИ ====================
        TimeSlotHelper: {
            // Обновляет поля слота в форме
            updateTimeSlotFields: function(slotId, displayText) {
                const timeSlotIdInput = document.getElementById('id_time_slot_id');
                const timeSlotDisplay = document.getElementById('time_slot_display');

                if (timeSlotIdInput) {
                    timeSlotIdInput.value = slotId;
                }
                if (timeSlotDisplay) {
                    timeSlotDisplay.value = displayText;
                }
            },

            // Загружает доступные слоты
            loadAvailableSlots: function(options) {
                const timeSlotSelect = document.getElementById(options.selectId);
                if (!timeSlotSelect || !options.date) return;

                timeSlotSelect.innerHTML = '<option value="">Загрузка...</option>';
                timeSlotSelect.disabled = true;

                fetch(options.apiUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': options.csrfToken
                    },
                    body: JSON.stringify({
                        doctor_id: options.doctorId,
                        date: options.date,
                        current_slot_id: options.currentSlotId,
                        current_appointment_id: options.currentAppointmentId
                    })
                })
                .then(response => response.json())
                .then(data => {
                    timeSlotSelect.innerHTML = '<option value="">Выберите временной слот</option>';

                    if (data.slots && data.slots.length > 0) {
                        data.slots.forEach(slot => {
                            const option = document.createElement('option');
                            option.value = slot.id;
                            option.textContent = `${slot.time} (${slot.cabinet})${slot.is_current ? ' - текущий' : ''}`;
                            timeSlotSelect.appendChild(option);
                        });

                        // Автоматически выбираем текущий слот
                        const currentSlotOption = timeSlotSelect.querySelector(`option[value="${options.currentSlotId}"]`);
                        if (currentSlotOption) {
                            timeSlotSelect.value = options.currentSlotId;
                            if (options.onSlotSelect) {
                                options.onSlotSelect(options.currentSlotId, currentSlotOption.textContent);
                            }
                        }
                    }

                    timeSlotSelect.disabled = false;
                })
                .catch(error => {
                    console.error('Error loading slots:', error);
                    timeSlotSelect.innerHTML = '<option value="">Ошибка загрузки слотов</option>';
                    timeSlotSelect.disabled = false;
                });
            }
        },

        // ==================== КОМПОНЕНТ ВЫБОРА ВРЕМЕНИ ====================
        TimeSlotSelector: {
            create: function(options) {
                const selector = {
                    containerId: options.containerId,
                    apiUrl: options.apiUrl,
                    csrfToken: options.csrfToken,
                    doctorId: options.doctorId,
                    currentSlotId: options.currentSlotId || null,
                    currentAppointmentId: options.currentAppointmentId || null,
                    onSlotSelect: options.onSlotSelect || function() {},

                    container: null,
                    selectedSlotId: null,
                    selectedSlotDisplay: '',

                    initialize: function() {
                        this.container = document.getElementById(this.containerId);
                        if (!this.container) {
                            console.error(`Container #${this.containerId} not found`);
                            return;
                        }

                        this.render();
                        this.bindEvents();

                        // Устанавливаем начальную дату если есть
                        if (options.initialDate) {
                            this.setDate(options.initialDate);
                        }
                    },

                    render: function() {
                        this.container.innerHTML = `
                            <div class="timeslot-selector">
                                <div class="card">
                                    <div class="card-header bg-light">
                                        <h6 class="mb-0">Выбор времени приема</h6>
                                    </div>
                                    <div class="card-body">
                                        <div class="row mb-3">
                                            <div class="col-md-6">
                                                <label for="timeslot-date-${this.containerId}" class="form-label">
                                                    Дата приема *
                                                </label>
                                                <input type="date"
                                                       id="timeslot-date-${this.containerId}"
                                                       class="form-control"
                                                       required>
                                                <div class="form-text">
                                                    Выберите дату приема
                                                </div>
                                            </div>
                                            <div class="col-md-6">
                                                <label for="timeslot-select-${this.containerId}" class="form-label">
                                                    Временной слот *
                                                </label>
                                                <select id="timeslot-select-${this.containerId}" class="form-select" disabled>
                                                    <option value="">Сначала выберите дату</option>
                                                </select>
                                                <div class="form-text">
                                                    Доступные слоты врача
                                                </div>
                                            </div>
                                        </div>

                                        <!-- Информация о выбранном слоте -->
                                        <div id="timeslot-info-${this.containerId}" class="alert alert-info" style="display: none;">
                                            <i class="fas fa-check-circle"></i>
                                            <strong>Выбран:</strong>
                                            <span id="timeslot-display-${this.containerId}"></span>
                                            <input type="hidden" id="selected-slot-id-${this.containerId}">
                                        </div>

                                        <!-- Сообщения об ошибках -->
                                        <div id="timeslot-error-${this.containerId}" class="alert alert-danger" style="display: none;"></div>
                                    </div>
                                </div>
                            </div>
                        `;
                    },

                    bindEvents: function() {
                        const dateInput = document.getElementById(`timeslot-date-${this.containerId}`);
                        const slotSelect = document.getElementById(`timeslot-select-${this.containerId}`);

                        if (dateInput) {
                            // Устанавливаем минимальную дату - сегодня
                            const today = new Date().toISOString().split('T')[0];
                            dateInput.min = today;

                            dateInput.addEventListener('change', (e) => {
                                this.loadSlots(e.target.value);
                            });
                        }

                        if (slotSelect) {
                            slotSelect.addEventListener('change', (e) => {
                                this.handleSlotSelection(e.target.value);
                            });
                        }
                    },

                    loadSlots: async function(date) {
                        const slotSelect = document.getElementById(`timeslot-select-${this.containerId}`);
                        const errorDiv = document.getElementById(`timeslot-error-${this.containerId}`);

                        if (!slotSelect) return;

                        // Показываем загрузку
                        slotSelect.innerHTML = '<option value="">Загрузка...</option>';
                        slotSelect.disabled = true;
                        errorDiv.style.display = 'none';

                        try {
                            const response = await fetch(this.apiUrl, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': this.csrfToken
                                },
                                body: JSON.stringify({
                                    doctor_id: this.doctorId,
                                    date: date,
                                    current_slot_id: this.currentSlotId,
                                    current_appointment_id: this.currentAppointmentId
                                })
                            });

                            const data = await response.json();

                            if (!response.ok) {
                                throw new Error(data.error || 'Ошибка загрузки слотов');
                            }

                            this.renderSlots(data.slots || []);

                        } catch (error) {
                            console.error('Error loading slots:', error);
                            this.showError(`Ошибка при загрузке слотов: ${error.message}`);
                        }
                    },

                    renderSlots: function(slots) {
                        const slotSelect = document.getElementById(`timeslot-select-${this.containerId}`);
                        if (!slotSelect) return;

                        slotSelect.innerHTML = '<option value="">Выберите временной слот</option>';

                        if (slots.length === 0) {
                            slotSelect.innerHTML = '<option value="">Нет доступных слотов на выбранную дату</option>';
                            slotSelect.disabled = false;
                            return;
                        }

                        slots.forEach(slot => {
                            const option = document.createElement('option');
                            option.value = slot.id;
                            option.textContent = `${slot.time} (${slot.cabinet})`;
                            if (slot.is_current) {
                                option.textContent += ' - текущий';
                            }
                            slotSelect.appendChild(option);
                        });

                        slotSelect.disabled = false;

                        // Автоматически выбираем текущий слот если он есть
                        if (this.currentSlotId) {
                            const currentSlotOption = slotSelect.querySelector(`option[value="${this.currentSlotId}"]`);
                            if (currentSlotOption) {
                                slotSelect.value = this.currentSlotId;
                                this.handleSlotSelection(this.currentSlotId);
                            }
                        }
                    },

                    handleSlotSelection: function(slotId) {
                        const slotSelect = document.getElementById(`timeslot-select-${this.containerId}`);
                        const infoDiv = document.getElementById(`timeslot-info-${this.containerId}`);
                        const displaySpan = document.getElementById(`timeslot-display-${this.containerId}`);

                        if (!slotSelect || !infoDiv || !displaySpan) return;

                        const selectedOption = slotSelect.options[slotSelect.selectedIndex];

                        if (selectedOption && selectedOption.value) {
                            this.selectedSlotId = slotId;
                            this.selectedSlotDisplay = selectedOption.textContent;

                            // Обновляем отображение
                            displaySpan.textContent = selectedOption.textContent;
                            infoDiv.style.display = 'block';

                            // Вызываем коллбэк
                            this.onSlotSelect({
                                id: slotId,
                                display: selectedOption.textContent,
                                time: selectedOption.textContent.split(' (')[0],
                                date: document.getElementById(`timeslot-date-${this.containerId}`)?.value
                            });
                        } else {
                            infoDiv.style.display = 'none';
                            this.selectedSlotId = null;
                            this.selectedSlotDisplay = '';
                        }
                    },

                    showError: function(message) {
                        const errorDiv = document.getElementById(`timeslot-error-${this.containerId}`);
                        if (errorDiv) {
                            errorDiv.textContent = message;
                            errorDiv.style.display = 'block';
                        }
                    },

                    getSelectedSlot: function() {
                        if (!this.selectedSlotId) return null;

                        return {
                            id: this.selectedSlotId,
                            display: this.selectedSlotDisplay,
                            date: document.getElementById(`timeslot-date-${this.containerId}`)?.value
                        };
                    },

                    setDate: function(date) {
                        const dateInput = document.getElementById(`timeslot-date-${this.containerId}`);
                        if (dateInput) {
                            dateInput.value = date;
                            this.loadSlots(date);
                        }
                    },

                    toggle: function(show = true) {
                        this.container.style.display = show ? 'block' : 'none';
                    }
                };

                selector.initialize();
                return selector;
            }
        }
    };

})();