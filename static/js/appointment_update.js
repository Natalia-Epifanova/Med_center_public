document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing appointment update form...');

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

    // Инициализация менеджера типов записей
    const appointmentTypeManager = window.AppointmentUtils.AppointmentTypeManager.create({
        radios: document.querySelectorAll('input[name="appointment_type"]'),
        additionalServiceSection: document.getElementById('additionalServiceSection'),
        twoSlotsSection: document.getElementById('twoSlotsSection'),
        additionalServiceSelect: document.getElementById('id_additional_service'),
        mainServiceSelect: document.getElementById('id_service')
    });

    // Инициализация обновления суммы
    window.AppointmentUtils.TotalSumUpdater.initialize('id_service', 'id_total_sum');

    // === ЛОГИКА ДЛЯ ВЫБОРА СЛОТОВ ===

    // Функция для обновления полей слота
    function updateTimeSlotFields(slotId, displayText) {
        const timeSlotIdInput = document.getElementById('id_time_slot_id');
        const timeSlotDisplay = document.getElementById('time_slot_display');

        if (timeSlotIdInput) {
            timeSlotIdInput.value = slotId;
        }
        if (timeSlotDisplay) {
            timeSlotDisplay.value = displayText;
        }
    }

    // Функция для загрузки доступных слотов
    function loadAvailableSlots(date) {
        const timeSlotSelect = document.getElementById('time_slot_select');
        if (!timeSlotSelect || !date) return;

        timeSlotSelect.innerHTML = '<option value="">Загрузка...</option>';
        timeSlotSelect.disabled = true;

        fetch(availableSlotsUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                doctor_id: doctorId,
                date: date,
                current_slot_id: currentSlotId,
                current_appointment_id: currentAppointmentId
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
                const currentSlotOption = timeSlotSelect.querySelector(`option[value="${currentSlotId}"]`);
                if (currentSlotOption) {
                    timeSlotSelect.value = currentSlotId;
                    updateTimeSlotFields(currentSlotId, currentSlotOption.textContent);
                }
            }

            timeSlotSelect.disabled = false;
        })
        .catch(error => {
            timeSlotSelect.innerHTML = '<option value="">Ошибка загрузки слотов</option>';
            timeSlotSelect.disabled = false;
        });
    }

    // Обработка изменения даты
    const appointmentDateInput = document.getElementById('id_appointment_date');
    if (appointmentDateInput) {
        appointmentDateInput.addEventListener('change', function() {
            loadAvailableSlots(this.value);
        });
    }

    // Обработка изменения выбора времени
    const timeSlotSelect = document.getElementById('time_slot_select');
    if (timeSlotSelect) {
        timeSlotSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            if (selectedOption && selectedOption.value) {
                updateTimeSlotFields(selectedOption.value, selectedOption.textContent);
            }
        });
    }

    // Загружаем слоты для текущей даты при загрузке
    if (appointmentDateInput && appointmentDateInput.value) {
        setTimeout(() => {
            loadAvailableSlots(appointmentDateInput.value);
        }, 500);
    }

    console.log('Appointment update form initialized successfully');
});