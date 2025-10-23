function checkProceduralAvailability(date, startTime, endTime, callback) {
    fetch('/timetable/api/check-procedural-availability/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            date: date,
            start_time: startTime,
            end_time: endTime,
            current_appointment_id: currentAppointmentId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (callback) callback(data);
    })
    .catch(error => {
        console.error('Error checking procedural availability:', error);
        if (callback) callback({ is_available: false, error: error.message });
    });
}

// Функция для получения времени слота по ID
function getSlotTime(slotId) {
    const option = timeSlotSelect.querySelector(`option[value="${slotId}"]`);
    if (option) {
        return option.textContent.split(' (')[0]; // Возвращаем только время
    }
    return null;
}

// Обработка изменения временного слота с проверкой процедурного кабинета
if (timeSlotSelect) {
    timeSlotSelect.addEventListener('change', function() {
        const selectedSlotId = this.value;

        // Обновляем скрытое поле формы
        timeSlotHidden.value = selectedSlotId;
        updateSlotInfo();

        // Проверяем доступность процедурного кабинета если галочка установлена
        const needsProcedural = document.getElementById('id_needs_procedural');
        if (needsProcedural && needsProcedural.checked && selectedSlotId) {
            const appointmentDate = appointmentDateInput.value;
            const slotTime = getSlotTime(selectedSlotId);

            if (appointmentDate && slotTime) {
                const [startTime, endTime] = slotTime.split('-');

                // Добавляем секунды для формата времени
                const startTimeWithSeconds = startTime.trim() + ':00';
                const endTimeWithSeconds = endTime.trim() + ':00';

                console.log('Checking procedural availability for:', appointmentDate, startTimeWithSeconds, endTimeWithSeconds);

                checkProceduralAvailability(appointmentDate, startTimeWithSeconds, endTimeWithSeconds, function(result) {
                    if (!result.is_available) {
                        const warningDiv = document.getElementById('proceduralWarning');
                        if (!warningDiv) {
                            const newWarning = document.createElement('div');
                            newWarning.id = 'proceduralWarning';
                            newWarning.className = 'alert alert-warning mt-2';
                            newWarning.innerHTML = `
                                <i class="fas fa-exclamation-triangle"></i>
                                <strong>Внимание!</strong> Выбранное время в процедурном кабинете занято.
                                ${result.occupied_slots && result.occupied_slots.length > 0 ?
                                    `Занято: ${result.occupied_slots.map(slot => slot.time).join(', ')}` : ''}
                                <br>При сохранении записи галочка "Занять окошко в процедурном кабинете" будет снята.
                            `;
                            timeSlotSelect.parentNode.appendChild(newWarning);
                        }
                    } else {
                        const warningDiv = document.getElementById('proceduralWarning');
                        if (warningDiv) {
                            warningDiv.remove();
                        }
                    }
                });
            }
        }
    });
}

// Обработка изменения галочки процедурного кабинета
const needsProceduralCheckbox = document.getElementById('id_needs_procedural');
if (needsProceduralCheckbox) {
    needsProceduralCheckbox.addEventListener('change', function() {
        const warningDiv = document.getElementById('proceduralWarning');
        if (warningDiv) {
            warningDiv.remove();
        }

        // Если галочка установлена, проверяем доступность текущего слота
        if (this.checked && timeSlotSelect.value) {
            const appointmentDate = appointmentDateInput.value;
            const slotTime = getSlotTime(timeSlotSelect.value);

            if (appointmentDate && slotTime) {
                const [startTime, endTime] = slotTime.split('-');
                const startTimeWithSeconds = startTime.trim() + ':00';
                const endTimeWithSeconds = endTime.trim() + ':00';

                checkProceduralAvailability(appointmentDate, startTimeWithSeconds, endTimeWithSeconds, function(result) {
                    if (!result.is_available) {
                        this.checked = false;
                        alert('Невозможно занять окошко в процедурном кабинете: выбранное время уже занято. Пожалуйста, выберите другое время.');
                    }
                }.bind(this));
            }
        }
    });
}

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

document.addEventListener('DOMContentLoaded', function() {
    const appointmentTypeRadios = document.querySelectorAll('input[name="appointment_type"]');
    const additionalServiceSection = document.getElementById('additionalServiceSection');
    const twoSlotsSection = document.getElementById('twoSlotsSection');
    const additionalServiceSelect = document.getElementById('id_additional_service');
    const mainServiceSelect = document.getElementById('id_service');
    const timeSlotSelect = document.getElementById('time_slot_select');
    const timeSlotHidden = document.getElementById('id_time_slot');
    const appointmentDateInput = document.getElementById('id_appointment_date');
    const phoneInput = document.getElementById('id_phone_number');

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
    // Функция для загрузки доступных слотов
    function loadAvailableSlots(date) {
        if (!timeSlotSelect || !date) return;

        console.log('Loading slots for date:', date, 'doctor:', doctorId);

        // Показываем загрузку
        timeSlotSelect.innerHTML = '<option value="">Загрузка...</option>';
        timeSlotSelect.disabled = true;

        // Отправляем запрос на сервер
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
                return response.text().then(text => {
                    console.error('Server response:', text);
                    throw new Error(`HTTP error! status: ${response.status}, response: ${text}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Received slots data:', data);

            timeSlotSelect.innerHTML = '<option value="">Выберите временной слот</option>';

            if (data.error) {
                console.error('API error:', data.error);
                let errorMessage = 'Ошибка загрузки слотов';
                if (data.error.includes('Неверный формат даты')) {
                    errorMessage = 'Неверный формат даты';
                }
                timeSlotSelect.innerHTML = `<option value="">${errorMessage}</option>`;
                timeSlotHidden.value = '';
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

                // Автоматически выбираем текущий слот, если он есть в результатах
                const currentSlotExists = data.slots.some(slot => slot.id == currentSlotId);
                if (currentSlotExists) {
                    timeSlotSelect.value = currentSlotId;
                    timeSlotHidden.value = currentSlotId;
                    console.log('Auto-selected current slot:', currentSlotId);
                } else {
                    // Если текущий слот не в результатах, выбираем первый доступный
                    timeSlotSelect.value = data.slots[0].id;
                    timeSlotHidden.value = data.slots[0].id;
                    console.log('Selected first available slot:', data.slots[0].id);
                }
            } else {
                console.log('No slots available for selected date');
                timeSlotSelect.innerHTML = '<option value="">Нет доступных слотов на выбранную дату</option>';
                timeSlotHidden.value = '';
            }

            timeSlotSelect.disabled = false;
            updateSlotInfo();
        })
        .catch(error => {
            console.error('Error loading slots:', error);
            console.error('Error details:', error.message);
            timeSlotSelect.innerHTML = '<option value="">Ошибка загрузки слотов</option>';
            timeSlotSelect.disabled = false;
            timeSlotHidden.value = '';
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
        if (selectedOption.value && selectedOption.value !== '') {
            const timeText = selectedOption.textContent.split(' (')[0];
            document.getElementById('currentSlotTime').textContent = timeText;
            document.getElementById('nextSlotTime').textContent = 'будет определен автоматически';
        } else {
            document.getElementById('currentSlotTime').textContent = 'не выбран';
            document.getElementById('nextSlotTime').textContent = 'не доступен';
        }
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
            // Обновляем скрытое поле формы
            timeSlotHidden.value = this.value;
            updateSlotInfo();

            const twoSlotsRadio = document.querySelector('input[name="appointment_type"][value="two_slots"]');
            if (twoSlotsRadio && twoSlotsRadio.checked) {
                updateSlotInfo();
            }
        });
    }

    // Обработка изменения типа записи
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

    // Обновляем дополнительные услуги при изменении основной услуги
    if (mainServiceSelect) {
        mainServiceSelect.addEventListener('change', function() {
            if (additionalServiceSection.style.display === 'block') {
                populateAdditionalServices();
            }
        });
    }

    // Инициализация при загрузке
    const checkedRadio = document.querySelector('input[name="appointment_type"]:checked');
    if (checkedRadio) {
        checkedRadio.dispatchEvent(new Event('change'));
    }

    // Загружаем слоты для текущей даты при загрузке страницы
    if (appointmentDateInput && appointmentDateInput.value) {
        console.log('Initial load for date:', appointmentDateInput.value);
        setTimeout(() => {
            loadAvailableSlots(appointmentDateInput.value);
        }, 100);
    }
});