document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DEBUG: Appointment Form Loaded ===');

    // Проверяем, что утилиты загружены
    if (!window.AppointmentUtils) {
        console.error('AppointmentUtils не загружен');
        return;
    }

    // 1. Инициализация форматирования телефона
    const phoneInput = document.getElementById('id_phone_number');
    if (phoneInput) {
        window.AppointmentUtils.PhoneFormatter.initialize(phoneInput);
    }

    // 2. Инициализация обновления суммы
    window.AppointmentUtils.TotalSumUpdater.initialize('id_service', 'id_total_sum');

    // 3. Инициализация проверки пациента
    initializePatientChecker();

    // 4. Инициализация процедурного кабинета для ОСНОВНОЙ услуги
    initializeProceduralManager();

    // 5. Инициализация процедурного кабинета для ДОПОЛНИТЕЛЬНОЙ услуги
    initializeProceduralManagerForAdditionalService();

    // 6. Инициализация менеджера цепочек
    initializeChainManager();

    // 7. Инициализация компонента изменения времени
    initializeTimeSlotSelector();

    // 8. Инициализация обработчиков типа записи
    initializeAppointmentTypeManager();

    // 9. Настройка чекбокса процедурного кабинета для второй услуги
    setupAdditionalProceduralCheckbox();
});

function initializePatientChecker() {
    if (!window.AppointmentUtils || !window.AppointmentUtils.PatientChecker) {
        console.error('PatientChecker не доступен');
        return;
    }

    // Создаем экземпляр проверки пациента
    const patientChecker = window.AppointmentUtils.PatientChecker.create({
        checkPatientUrl: checkPatientUrl,
        csrfToken: csrfToken
    });

    // Инициализируем кнопку проверки пациента
    patientChecker.initializeCheckButton('checkPatientBtn', 'patientCheckResult');
}

function initializeProceduralManager() {
    if (!window.AppointmentUtils || !window.AppointmentUtils.ProceduralManager) {
        console.error('ProceduralManager не доступен');
        return;
    }

    // Инициализируем обработчик процедурного кабинета для основной услуги
    window.AppointmentUtils.ProceduralManager.initialize('id_service', 'id_needs_procedural');
}

function initializeAppointmentTypeManager() {
    // Находим элементы для основного типа записи
    const radios = document.querySelectorAll('input[name="appointment_chain_type"]');
    const additionalServiceSection = document.getElementById('additionalServiceSection');
    const twoSlotsSection = document.getElementById('twoSlotsSection');
    const additionalServiceSelect = document.getElementById('id_additional_service');
    const mainServiceSelect = document.getElementById('id_service');

    if (radios.length > 0 && additionalServiceSection && twoSlotsSection) {
        initializeAppointmentTypeManagerLegacy();
    }
}

function setupAdditionalProceduralCheckbox() {
    const additionalProceduralCheckbox = document.getElementById('id_needs_procedural_additional');
    const additionalProceduralVisibleCheckbox = document.getElementById('needs_procedural_additional_checkbox');

    if (additionalProceduralVisibleCheckbox && additionalProceduralCheckbox) {
        console.log('Setting up additional procedural checkbox');

        // Обновляем скрытое поле при изменении видимого чекбокса
        additionalProceduralVisibleCheckbox.addEventListener('change', function() {
            // Обновляем значение скрытого поля
            additionalProceduralCheckbox.value = this.checked ? 'true' : 'false';
            console.log('Additional procedural checkbox changed to:', this.checked,
                       'hidden field value:', additionalProceduralCheckbox.value);
        });

        // Инициализируем значение при загрузке
        if (additionalProceduralVisibleCheckbox.checked) {
            additionalProceduralCheckbox.value = 'true';
        } else {
            additionalProceduralCheckbox.value = 'false';
        }

        // Также обновляем при отправке формы
        const appointmentForm = document.getElementById('appointmentForm');
        if (appointmentForm) {
            appointmentForm.addEventListener('submit', function() {
                // Убеждаемся, что значение синхронизировано
                additionalProceduralCheckbox.value =
                    additionalProceduralVisibleCheckbox.checked ? 'true' : 'false';
                console.log('Form submit - needs_procedural_additional:',
                           additionalProceduralCheckbox.value);
            });
        }
    } else {
        console.log('Additional procedural checkbox elements not found');
        console.log('Visible checkbox:', additionalProceduralVisibleCheckbox);
        console.log('Hidden field:', additionalProceduralCheckbox);
    }
}

function initializeAppointmentTypeManagerLegacy() {
    console.log('Initializing legacy appointment type manager');

    const radios = document.querySelectorAll('input[name="appointment_chain_type"]');
    const additionalServiceSection = document.getElementById('additionalServiceSection');
    const additionalProceduralSection = document.getElementById('additionalServiceProceduralSection');
    const twoSlotsSection = document.getElementById('twoSlotsSection');
    const additionalServiceSelect = document.getElementById('id_additional_service');
    const mainServiceSelect = document.getElementById('id_service');
    const sameDoctorSections = document.getElementById('sameDoctorSections');

    // Функция для заполнения дополнительных услуг
    function populateAdditionalServices() {
        if (!additionalServiceSelect || !mainServiceSelect) return;

        additionalServiceSelect.innerHTML = '<option value="">---------</option>';

        const mainOptions = mainServiceSelect.querySelectorAll('option');
        mainOptions.forEach(option => {
            if (option.value !== '') {
                const newOption = document.createElement('option');
                newOption.value = option.value;
                newOption.textContent = option.textContent;
                additionalServiceSelect.appendChild(newOption);
            }
        });
    }

    // Функция для обработки отображения секций
    function updateSectionsVisibility(value) {
        // Сначала скрываем все секции sameDoctorSections
        if (sameDoctorSections) {
            sameDoctorSections.style.display = 'none';
        }

        // Скрываем подсекции
        if (additionalServiceSection) {
            additionalServiceSection.style.display = 'none';
        }
        if (additionalProceduralSection) {
            additionalProceduralSection.style.display = 'none';
        }
        if (twoSlotsSection) {
            twoSlotsSection.style.display = 'none';
        }

        // Показываем нужные секции
        if (value === 'additional' || value === 'two_slots') {
            if (sameDoctorSections) {
                sameDoctorSections.style.display = 'block';
            }

            if (value === 'additional') {
                if (additionalServiceSection) {
                    additionalServiceSection.style.display = 'block';
                    populateAdditionalServices();

                    // Проверяем, есть ли выбранная услуга для показа процедурной секции
                    if (additionalServiceSelect && additionalServiceSelect.value) {
                        additionalProceduralSection.style.display = 'block';
                    }
                }
            } else if (value === 'two_slots') {
                if (twoSlotsSection) {
                    twoSlotsSection.style.display = 'block';
                }
            }
        }
    }

    // Обработчик изменения типа записи
    function handleAppointmentTypeChange(event) {
        const value = event.target.value;
        console.log('Appointment type changed to:', value);
        updateSectionsVisibility(value);
    }

    // Обработчик изменения дополнительной услуги
    function handleAdditionalServiceChange() {
        const additionalProceduralSection = document.getElementById('additionalServiceProceduralSection');
        if (!additionalProceduralSection) return;

        if (this.value) {
            additionalProceduralSection.style.display = 'block';
        } else {
            additionalProceduralSection.style.display = 'none';

            // Сбрасываем чекбокс процедурного кабинета
            const additionalProceduralCheckbox = document.getElementById('needs_procedural_additional_checkbox');
            if (additionalProceduralCheckbox) {
                additionalProceduralCheckbox.checked = false;
            }

            const hiddenField = document.getElementById('id_needs_procedural_additional');
            if (hiddenField) {
                hiddenField.value = 'false';
            }
        }
    }

    // Добавляем обработчики событий
    if (radios.length > 0) {
        radios.forEach(radio => {
            radio.addEventListener('change', handleAppointmentTypeChange);
        });

        // Триггерим изменение для выбранного радио
        const checkedRadio = document.querySelector('input[name="appointment_chain_type"]:checked');
        if (checkedRadio) {
            updateSectionsVisibility(checkedRadio.value);
        }
    }

    // Обновляем дополнительные услуги при изменении основной
    if (mainServiceSelect && additionalServiceSelect) {
        mainServiceSelect.addEventListener('change', () => {
            if (additionalServiceSection &&
                additionalServiceSection.style.display === 'block') {
                populateAdditionalServices();
            }
        });
    }

    // Обработчик изменения дополнительной услуги
    if (additionalServiceSelect) {
        additionalServiceSelect.addEventListener('change', handleAdditionalServiceChange);
    }
}

function initializeChainManager() {
    // ... существующий код без изменений ...
}

function initializeProceduralManagerForAdditionalService() {
    if (!window.AppointmentUtils || !window.AppointmentUtils.ProceduralManager) {
        console.error('ProceduralManager не доступен');
        return;
    }

    // Находим элементы для основной услуги
    const mainServiceSelect = document.getElementById('id_service');
    const mainProceduralCheckbox = document.getElementById('id_needs_procedural');

    // Находим элементы для дополнительной услуги
    const additionalServiceSelect = document.getElementById('id_additional_service');
    const additionalProceduralVisibleCheckbox = document.getElementById('needs_procedural_additional_checkbox');
    const additionalProceduralSection = document.getElementById('additionalServiceProceduralSection');
    const additionalProceduralHiddenField = document.getElementById('id_needs_procedural_additional');

    if (additionalServiceSelect && additionalProceduralVisibleCheckbox && additionalProceduralSection) {
        // Обработчик изменения дополнительной услуги
        additionalServiceSelect.addEventListener('change', function() {
            // Используем утилиту для проверки, нужен ли процедурный кабинет
            window.AppointmentUtils.ProceduralManager.updateProceduralCheckbox(
                this,
                additionalProceduralVisibleCheckbox
            );

            // Показываем/скрываем секцию процедурного кабинета
            if (this.value) {
                additionalProceduralSection.style.display = 'block';

                // Проверяем, нужен ли процедурный кабинет для этой услуги
                const selectedOption = this.options[this.selectedIndex];
                const serviceName = selectedOption.text.toLowerCase();

                // Определяем, нужно ли автоматически отмечать чекбокс
                const needsProcedural = serviceName.includes('блокада') ||
                                       serviceName.includes('укол') ||
                                       serviceName.includes('пункция') ||
                                       serviceName.includes('введение') ||
                                       serviceName.includes('инъекция') ||
                                       serviceName.includes('внутримышечно') ||
                                       serviceName.includes('внутрикожно') ||
                                       serviceName.includes('внутривенно');

                if (needsProcedural) {
                    if (!additionalProceduralVisibleCheckbox.checked) {
                        additionalProceduralVisibleCheckbox.checked = true;
                    }

                    // Обновляем скрытое поле
                    if (additionalProceduralHiddenField) {
                        additionalProceduralHiddenField.value = 'true';
                    }
                } else {
                    // Если услуга не требует процедурного кабинета
                    if (additionalProceduralVisibleCheckbox.checked) {
                        additionalProceduralVisibleCheckbox.checked = false;
                    }

                    // Обновляем скрытое поле
                    if (additionalProceduralHiddenField) {
                        additionalProceduralHiddenField.value = 'false';
                    }
                }
            } else {
                additionalProceduralSection.style.display = 'none';

                // Сбрасываем чекбокс
                if (additionalProceduralVisibleCheckbox.checked) {
                    additionalProceduralVisibleCheckbox.checked = false;
                }

                // Сбрасываем скрытое поле
                if (additionalProceduralHiddenField) {
                    additionalProceduralHiddenField.value = 'false';
                }
            }
        });

        // Проверяем при загрузке страницы
        if (additionalServiceSelect.value) {
            window.AppointmentUtils.ProceduralManager.updateProceduralCheckbox(
                additionalServiceSelect,
                additionalProceduralVisibleCheckbox
            );
            additionalProceduralSection.style.display = 'block';

            // Обновляем скрытое поле
            if (additionalProceduralHiddenField && additionalProceduralVisibleCheckbox.checked) {
                additionalProceduralHiddenField.value = 'true';
            }
        }
    }
}


function initializeTimeSlotSelector() {
    const changeTimeBtn = document.getElementById('change-time-btn');
    const selectorContainer = document.getElementById('timeslot-selector-container');
    const originalInfo = document.getElementById('original-slot-info');

    if (!changeTimeBtn || !selectorContainer || !originalInfo) {
        console.log('Time slot selector elements not found - skipping initialization');
        return;
    }

    let timeSlotSelector = null;

    // Проверяем, есть ли необходимые глобальные переменные
    if (!window.AppointmentUtils || !window.AppointmentUtils.TimeSlotSelector) {
        console.warn('AppointmentUtils.TimeSlotSelector not available');
        return;
    }

    if (!availableSlotsUrl || !doctorId || !csrfToken) {
        console.warn('Missing required variables for TimeSlotSelector:', {
            availableSlotsUrl: availableSlotsUrl,
            doctorId: doctorId,
            csrfToken: csrfToken ? 'exists' : 'missing'
        });
        return;
    }

    // Функция для форматирования даты
    function formatDate(dateString) {
        try {
            const date = new Date(dateString + 'T00:00:00');
            return date.toLocaleDateString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });
        } catch (error) {
            console.error('Error formatting date:', error);
            return dateString;
        }
    }

    // Инициализируем TimeSlotSelector
    timeSlotSelector = window.AppointmentUtils.TimeSlotSelector.create({
        containerId: 'timeslot-selector-container',
        apiUrl: availableSlotsUrl,
        csrfToken: csrfToken,
        doctorId: doctorId,
        currentSlotId: currentSlotId,
        currentAppointmentId: null, // Для создания записи нет текущей записи
        initialDate: originalDate,
        onSlotSelect: function(slotData) {
            console.log('Time slot selected:', slotData);

            if (slotData && slotData.id) {
                // Обновляем hidden поля формы
                const allowTimeChangeInput = document.getElementById('id_allow_time_change');
                const newTimeSlotIdInput = document.getElementById('id_new_time_slot_id');
                const newAppointmentDateInput = document.getElementById('id_new_appointment_date');

                if (allowTimeChangeInput) allowTimeChangeInput.value = 'true';
                if (newTimeSlotIdInput) newTimeSlotIdInput.value = slotData.id;
                if (newAppointmentDateInput && slotData.date) newAppointmentDateInput.value = slotData.date;

                // Обновляем отображение оригинального времени
                const originalDateSpan = document.getElementById('original-date');
                const originalTimeSpan = document.getElementById('original-time');
                const originalCabinetSpan = document.getElementById('original-cabinet');

                if (originalDateSpan) {
                    originalDateSpan.textContent = formatDate(slotData.date || originalDate);
                }

                if (originalTimeSpan && slotData.display) {
                    // Извлекаем время из формата "HH:MM-HH:MM (Каб. X)"
                    const timeMatch = slotData.display.match(/(\d{1,2}:\d{2}-\d{1,2}:\d{2})/);
                    if (timeMatch) {
                        originalTimeSpan.textContent = timeMatch[1];
                    } else {
                        originalTimeSpan.textContent = slotData.display;
                    }
                }

                if (originalCabinetSpan && slotData.display) {
                    // Извлекаем кабинет из формата
                    const cabinetMatch = slotData.display.match(/\(([^)]+)\)/);
                    if (cabinetMatch) {
                        originalCabinetSpan.textContent = cabinetMatch[1];
                    }
                }

                console.log('Updated time slot selection');
            }
        }
    });

    // Обработчик кнопки "Изменить время"
    changeTimeBtn.addEventListener('click', function() {
        if (selectorContainer.style.display === 'none') {
            // Показываем селектор времени
            selectorContainer.style.display = 'block';
            originalInfo.style.display = 'none';
            changeTimeBtn.innerHTML = '<i class="fas fa-times"></i> Отменить изменение';
            changeTimeBtn.classList.remove('btn-outline-warning');
            changeTimeBtn.classList.add('btn-outline-danger');

            // Загружаем слоты если селектор еще не инициализирован
            if (timeSlotSelector) {
                timeSlotSelector.setDate(originalDate);
            }
        } else {
            // Скрываем селектор времени
            selectorContainer.style.display = 'none';
            originalInfo.style.display = 'block';
            changeTimeBtn.innerHTML = '<i class="fas fa-clock"></i> Изменить время';
            changeTimeBtn.classList.remove('btn-outline-danger');
            changeTimeBtn.classList.add('btn-outline-warning');

            // Сбрасываем выбор времени
            const allowTimeChangeInput = document.getElementById('id_allow_time_change');
            const newTimeSlotIdInput = document.getElementById('id_new_time_slot_id');
            const newAppointmentDateInput = document.getElementById('id_new_appointment_date');

            if (allowTimeChangeInput) allowTimeChangeInput.value = 'false';
            if (newTimeSlotIdInput) newTimeSlotIdInput.value = currentSlotId;
            if (newAppointmentDateInput) newAppointmentDateInput.value = originalDate;

            // Восстанавливаем оригинальное отображение
            const originalDateSpan = document.getElementById('original-date');
            const originalTimeSpan = document.getElementById('original-time');
            const originalCabinetSpan = document.getElementById('original-cabinet');

            if (originalDateSpan) {
                originalDateSpan.textContent = formatDate(originalDate);
            }

            if (originalTimeSpan) {
                originalTimeSpan.textContent = originalTime;
            }

            if (originalCabinetSpan) {
                originalCabinetSpan.textContent = originalCabinetName
                    ? `${originalCabinet} (${originalCabinetName})`
                    : originalCabinet;
            }
        }
    });

    // Инициализируем селектор времени при загрузке (но не показываем)
    console.log('Time slot selector initialized');
}