document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DEBUG: Appointment Form Loaded ===');

    // Проверяем, что утилиты загружены
    if (!window.AppointmentUtils) {
        console.error('AppointmentUtils не загружен');
        return;
    }

    // Инициализация форматирования телефона
    const phoneInput = document.getElementById('id_phone_number');
    if (phoneInput) {
        window.AppointmentUtils.PhoneFormatter.initialize(phoneInput);
    }

    // Автоматическая отметка процедурного кабинета для блокад
    const serviceSelect = document.getElementById('id_service');
    const needsProceduralCheckbox = document.getElementById('id_needs_procedural');

    if (serviceSelect && needsProceduralCheckbox) {
        serviceSelect.addEventListener('change', function() {
            if (window.AppointmentUtils.ServiceValidator.isMedicalBlockade(this)) {
                needsProceduralCheckbox.checked = true;
            }
        });

        // Инициализация при загрузке
        if (window.AppointmentUtils.ServiceValidator.isMedicalBlockade(serviceSelect)) {
            needsProceduralCheckbox.checked = true;
        }
    }

    // Проверка ограничений врача Пищелева
    if (serviceSelect) {
        serviceSelect.addEventListener('change', function() {
            window.AppointmentUtils.ServiceValidator.checkServiceRestrictions(this);
        });
        window.AppointmentUtils.ServiceValidator.checkServiceRestrictions(serviceSelect);
    }

    // Инициализация менеджера типов записей
    const appointmentTypeManager = window.AppointmentUtils.AppointmentTypeManager.create({
        radios: document.querySelectorAll('input[name="appointment_type"]'),
        additionalServiceSection: document.getElementById('additionalServiceSection'),
        twoSlotsSection: document.getElementById('twoSlotsSection'),
        additionalServiceSelect: document.getElementById('id_additional_service'),
        mainServiceSelect: serviceSelect
    });

    // Инициализация проверки пациента
    if (typeof checkPatientUrl !== 'undefined' && typeof csrfToken !== 'undefined') {
        const patientChecker = window.AppointmentUtils.PatientChecker.create({
            checkPatientUrl: checkPatientUrl,
            csrfToken: csrfToken
        });

        patientChecker.initializeCheckButton('checkPatientBtn', 'patientCheckResult');
    } else {
        console.warn('Patient check URL or CSRF token not defined');
    }

    // Инициализация обновления суммы
    window.AppointmentUtils.TotalSumUpdater.initialize('id_service', 'id_total_sum');

    // === ИНИЦИАЛИЗАЦИЯ ВЫБОРА ВРЕМЕНИ ===
    let timeSlotSelector = null;

    // Форматирует дату в русском формате
    function formatDate(dateString) {
        const date = new Date(dateString + 'T00:00:00');
        return date.toLocaleDateString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    }

    // Обновляет отображение выбранного времени
    function updateOriginalSlotDisplay(slotData) {
        const originalDateSpan = document.getElementById('original-date');
        const originalTimeSpan = document.getElementById('original-time');
        const originalCabinetSpan = document.getElementById('original-cabinet');

        if (originalDateSpan && originalTimeSpan && originalCabinetSpan) {
            // Парсим время из строки "HH:MM-HH:MM (Каб. X)"
            const match = slotData.display.match(/(\d{1,2}:\d{2}-\d{1,2}:\d{2})\s*\(Каб\.\s*(\d+)\)/);
            if (match) {
                const time = match[1];
                const cabinet = match[2];
                const date = slotData.date || originalDate;

                originalDateSpan.textContent = formatDate(date);
                originalTimeSpan.textContent = time;
                originalCabinetSpan.textContent = cabinet;
            }
        }
    }

    // Обработчик выбора слота
    function handleSlotSelection(slotData) {
        console.log('Slot selected:', slotData);

        if (slotData && slotData.id) {
            // Обновляем hidden поля формы
            document.getElementById('id_allow_time_change').value = 'true';
            document.getElementById('id_new_time_slot_id').value = slotData.id;
            document.getElementById('id_new_appointment_date').value = slotData.date;

            // Обновляем отображение
            updateOriginalSlotDisplay(slotData);

            console.log('Time changed to:', slotData.display, 'Date:', slotData.date);
        }
    }

    // Инициализируем TimeSlotSelector
    function initializeTimeSlotSelector() {
        if (!doctorId || !availableSlotsUrl) {
            console.warn('Doctor ID or API URL not defined for TimeSlotSelector');
            return;
        }

        timeSlotSelector = window.AppointmentUtils.TimeSlotSelector.create({
            containerId: 'timeslot-selector-container',
            apiUrl: availableSlotsUrl,
            csrfToken: csrfToken,
            doctorId: doctorId,
            currentSlotId: currentSlotId,
            currentAppointmentId: null, // Для создания записи нет текущей записи
            initialDate: originalDate,
            onSlotSelect: handleSlotSelection
        });
    }

    // Обработчик кнопки "Изменить время"
    const changeTimeBtn = document.getElementById('change-time-btn');
    if (changeTimeBtn) {
        changeTimeBtn.addEventListener('click', function() {
            const selectorContainer = document.getElementById('timeslot-selector-container');
            const originalInfo = document.getElementById('original-slot-info');

            if (selectorContainer.style.display === 'none') {
                // Показываем селектор времени
                selectorContainer.style.display = 'block';
                originalInfo.style.display = 'none';
                changeTimeBtn.innerHTML = '<i class="fas fa-times"></i> Отменить изменение';
                changeTimeBtn.classList.remove('btn-outline-warning');
                changeTimeBtn.classList.add('btn-outline-danger');

                // Инициализируем селектор если еще не инициализирован
                if (!timeSlotSelector) {
                    initializeTimeSlotSelector();
                }
            } else {
                // Скрываем селектор времени
                selectorContainer.style.display = 'none';
                originalInfo.style.display = 'block';
                changeTimeBtn.innerHTML = '<i class="fas fa-clock"></i> Изменить время';
                changeTimeBtn.classList.remove('btn-outline-danger');
                changeTimeBtn.classList.add('btn-outline-warning');

                // Сбрасываем выбор времени
                document.getElementById('id_allow_time_change').value = 'false';
                document.getElementById('id_new_time_slot_id').value = currentSlotId;
                document.getElementById('id_new_appointment_date').value = originalDate;

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
    }

    // Инициализируем селектор времени при загрузке (но не показываем)
    initializeTimeSlotSelector();

    console.log('Event listeners initialized successfully');
});