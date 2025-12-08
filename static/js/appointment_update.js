document.addEventListener('DOMContentLoaded', function() {
    // Основные элементы
    const appointmentTypeRadios = document.querySelectorAll('input[name="appointment_type"]');
    const additionalServiceSection = document.getElementById('additionalServiceSection');
    const twoSlotsSection = document.getElementById('twoSlotsSection');
    const additionalServiceSelect = document.getElementById('id_additional_service');
    const mainServiceSelect = document.getElementById('id_service');
    const timeSlotSelect = document.getElementById('time_slot_select'); // Изменили ID
    const timeSlotDisplay = document.getElementById('time_slot_display');
    const timeSlotIdInput = document.getElementById('id_time_slot_id');
    const appointmentDateInput = document.getElementById('id_appointment_date');
    const phoneInput = document.getElementById('id_phone_number');

    console.log('Initializing appointment update form...');
    console.log('Available slots URL:', availableSlotsUrl);
    console.log('Doctor ID:', doctorId);
    console.log('Current slot ID:', currentSlotId);

    // Функция для обновления полей слота
    function updateTimeSlotFields(slotId, displayText) {
        if (timeSlotIdInput) {
            timeSlotIdInput.value = slotId;
            console.log('Set time_slot_id to:', slotId);
        }
        if (timeSlotDisplay) {
            timeSlotDisplay.value = displayText;
            console.log('Set time_slot_display to:', displayText);
        }
    }

    // Функция для загрузки доступных слотов
    function loadAvailableSlots(date) {
        if (!timeSlotSelect || !date) {
            console.error('Time slot select or date not found');
            return;
        }

        console.log('Loading slots for date:', date, 'doctor:', doctorId);

        // Показываем загрузку
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
        .then(response => {
            console.log('Response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Received data:', data);
            timeSlotSelect.innerHTML = '<option value="">Выберите временной слот</option>';

            if (data.error) {
                console.error('API error:', data.error);
                timeSlotSelect.innerHTML = '<option value="">Ошибка загрузки слотов</option>';
                return;
            }

            if (data.slots && data.slots.length > 0) {
                console.log(`Found ${data.slots.length} slots`);

                data.slots.forEach(slot => {
                    const option = document.createElement('option');
                    option.value = slot.id;
                    option.textContent = `${slot.time} (${slot.cabinet})${slot.is_current ? ' - текущий' : ''}`;
                    timeSlotSelect.appendChild(option);
                });

                // Автоматически выбираем текущий слот, если он есть
                const currentSlotOption = timeSlotSelect.querySelector(`option[value="${currentSlotId}"]`);
                if (currentSlotOption) {
                    timeSlotSelect.value = currentSlotId;
                    updateTimeSlotFields(currentSlotId, currentSlotOption.textContent);
                    console.log('Auto-selected current slot:', currentSlotId);
                } else if (data.slots.length > 0) {
                    // Иначе выбираем первый доступный
                    timeSlotSelect.value = data.slots[0].id;
                    updateTimeSlotFields(data.slots[0].id, `${data.slots[0].time} (${data.slots[0].cabinet})`);
                    console.log('Selected first available slot:', data.slots[0].id);
                }
            } else {
                console.log('No slots available for selected date');
                timeSlotSelect.innerHTML = '<option value="">Нет доступных слотов на выбранную дату</option>';
            }

            timeSlotSelect.disabled = false;
            updateSlotInfo();
        })
        .catch(error => {
            console.error('Error loading slots:', error);
            timeSlotSelect.innerHTML = '<option value="">Ошибка загрузки слотов</option>';
            timeSlotSelect.disabled = false;
        });
    }

    // Функция для заполнения дополнительной услуги
    function populateAdditionalServices() {
        if (!additionalServiceSelect) return;

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

    // Функция для обновления информации о слотах
    function updateSlotInfo() {
        if (!timeSlotSelect || !twoSlotsSection) return;

        const selectedOption = timeSlotSelect.options[timeSlotSelect.selectedIndex];
        if (selectedOption && selectedOption.value && selectedOption.value !== '') {
            const timeText = selectedOption.textContent.split(' (')[0];
            if (document.getElementById('currentSlotTime')) {
                document.getElementById('currentSlotTime').textContent = timeText;
            }
            if (document.getElementById('nextSlotTime')) {
                document.getElementById('nextSlotTime').textContent = 'будет определен автоматически';
            }
        } else {
            if (document.getElementById('currentSlotTime')) {
                document.getElementById('currentSlotTime').textContent = 'не выбран';
            }
            if (document.getElementById('nextSlotTime')) {
                document.getElementById('nextSlotTime').textContent = 'не доступен';
            }
        }
    }

    // Функция для форматирования номера телефона
    function formatPhoneNumber(input) {
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
    }

    // Обработка изменения даты
    if (appointmentDateInput) {
        appointmentDateInput.addEventListener('change', function() {
            console.log('Date changed to:', this.value);
            loadAvailableSlots(this.value);
        });
    }

    // Обработка изменения выбора времени
    if (timeSlotSelect) {
        timeSlotSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            if (selectedOption && selectedOption.value) {
                updateTimeSlotFields(selectedOption.value, selectedOption.textContent);
            } else {
                updateTimeSlotFields('', '');
            }

            updateSlotInfo();
        });
    }

    // Обработка изменения типа записи
    if (appointmentTypeRadios) {
        appointmentTypeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                if (additionalServiceSection) {
                    additionalServiceSection.style.display = 'none';
                }
                if (twoSlotsSection) {
                    twoSlotsSection.style.display = 'none';
                }

                if (this.value === 'additional' && additionalServiceSection) {
                    additionalServiceSection.style.display = 'block';
                    populateAdditionalServices();
                } else if (this.value === 'two_slots' && twoSlotsSection) {
                    twoSlotsSection.style.display = 'block';
                    updateSlotInfo();
                }
            });
        });
    }

    // Форматирование номера телефона
    if (phoneInput) {
        phoneInput.addEventListener('input', function() {
            formatPhoneNumber(this);
        });

        phoneInput.addEventListener('blur', function() {
            formatPhoneNumber(this);
        });

        if (phoneInput.value) {
            formatPhoneNumber(phoneInput);
        }
    }

    // Инициализация при загрузке
    const checkedRadio = document.querySelector('input[name="appointment_type"]:checked');
    if (checkedRadio) {
        checkedRadio.dispatchEvent(new Event('change'));
    }

    // Загружаем слоты для текущей даты при загрузке страницы
    if (appointmentDateInput && appointmentDateInput.value) {
        console.log('Initial load for date:', appointmentDateInput.value);
        // Даем время для полной загрузки DOM
        setTimeout(() => {
            loadAvailableSlots(appointmentDateInput.value);
        }, 500);
    } else {
        // Если дата не установлена, устанавливаем текущую дату
        const today = new Date().toISOString().split('T')[0];
        if (appointmentDateInput) {
            appointmentDateInput.value = today;
            setTimeout(() => {
                loadAvailableSlots(today);
            }, 500);
        }
    }
});