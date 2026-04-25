function initializeTimeSlotSelector() {
    const changeTimeBtn = document.getElementById('change-time-btn');
    const selectorContainer = document.getElementById('timeslot-selector-container');
    const originalInfo = document.getElementById('original-slot-info');
    const timeChangeButtons = document.getElementById('time-change-buttons');
    const confirmBtn = document.getElementById('confirm-time-change-btn');
    const cancelBtn = document.getElementById('cancel-time-change-btn');

    if (!changeTimeBtn || !selectorContainer || !originalInfo || !timeChangeButtons) return;

    if (!selectorContainer.querySelector('.timeslot-selector')) {
        selectorContainer.innerHTML = `
            <div class="timeslot-selector card mt-3">
                <div class="card-header bg-light">
                    <h6 class="mb-0">Выбор нового времени приема</h6>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <label for="timeslot-date" class="form-label">
                                Дата приема *
                            </label>
                            <input type="date" id="timeslot-date" class="form-control" required>
                            <div class="form-text">Выберите новую дату приема</div>
                        </div>
                        <div class="col-md-6">
                            <label for="timeslot-select" class="form-label">
                                Временной слот *
                            </label>
                            <select id="timeslot-select" class="form-select" disabled>
                                <option value="">Сначала выберите дату</option>
                            </select>
                            <div class="form-text">Выберите доступное время</div>
                        </div>
                    </div>
                    <div id="timeslot-info" class="alert alert-info mt-3" style="display: none;">
                        <i class="fas fa-check-circle"></i>
                        <strong>Выбрано новое время:</strong>
                        <span id="timeslot-display"></span>
                    </div>
                </div>
            </div>
        `;
    }

    let timeSlotSelector = null;
    let isChangingTime = false;
    let originalSlotData = {
        date: originalDate,
        time: originalTime,
        cabinet: originalCabinet,
        cabinetName: originalCabinetName
    };
    let selectedSlot = null;

    if (!window.AppointmentUtils || !window.AppointmentUtils.TimeSlotSelector) return;
    if (!availableSlotsUrl || !doctorId || !csrfToken) return;

    function formatDate(dateString) {
        try {
            const date = new Date(dateString + 'T00:00:00');
            return date.toLocaleDateString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });
        } catch (error) {
            return dateString;
        }
    }

    async function getNextSlotInfo(slotId, date) {
        if (!slotId || !date) return null;

        try {
            const response = await fetch('/appointments/api/get-next-slot/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    doctor_id: doctorId,
                    date: date,
                    current_slot_id: slotId
                })
            });

            if (!response.ok) return null;
            return await response.json();
        } catch (error) {
            return null;
        }
    }

    async function updateNextSlotInfo(slotId, date) {
        const currentSlotSpan = document.getElementById('current-slot-time');
        const nextSlotSpan = document.getElementById('next-slot-time');
        const twoSlotsSection = document.getElementById('twoSlotsSection');

        if (!currentSlotSpan || !nextSlotSpan || !twoSlotsSection) return;

        if (selectedSlot && selectedSlot.display) {
            const timeMatch = selectedSlot.display.match(/(\d{1,2}:\d{2}-\d{1,2}:\d{2})/);
            if (timeMatch) {
                currentSlotSpan.textContent = timeMatch[1];
            } else {
                currentSlotSpan.textContent = selectedSlot.display;
            }
        } else {
            currentSlotSpan.textContent = originalSlotData.time;
        }

        const nextSlotInfo = await getNextSlotInfo(slotId, date);

        if (nextSlotInfo && nextSlotInfo.success && nextSlotInfo.next_slot) {
            const nextSlot = nextSlotInfo.next_slot;
            nextSlotSpan.textContent = `${nextSlot.start_time}-${nextSlot.end_time}`;
            nextSlotSpan.style.color = '';
        } else {
            nextSlotSpan.textContent = 'не доступен';
            nextSlotSpan.style.color = 'red';
        }

        const twoSlotsRadio = document.querySelector('input[name="appointment_chain_type"][value="two_slots"]');
        if (twoSlotsRadio && twoSlotsRadio.checked) {
            twoSlotsSection.style.display = 'block';
        }
    }

    function updateOriginalDisplay(slotData) {
        const originalDateSpan = document.getElementById('original-date');
        const originalTimeSpan = document.getElementById('original-time');
        const originalCabinetSpan = document.getElementById('original-cabinet');

        if (slotData) {
            if (originalDateSpan && slotData.date) {
                originalDateSpan.textContent = formatDate(slotData.date);
            }

            if (originalTimeSpan && slotData.display) {
                const timeMatch = slotData.display.match(/(\d{1,2}:\d{2}-\d{1,2}:\d{2})/);
                if (timeMatch) {
                    originalTimeSpan.textContent = timeMatch[1];
                } else {
                    originalTimeSpan.textContent = slotData.display;
                }
            }

            if (originalCabinetSpan && slotData.display) {
                const cabinetMatch = slotData.display.match(/\(([^)]+)\)/);
                if (cabinetMatch) {
                    originalCabinetSpan.textContent = cabinetMatch[1];
                }
            }

            updateNextSlotInfo(slotData.id, slotData.date);
        } else {
            if (originalDateSpan) {
                originalDateSpan.textContent = formatDate(originalSlotData.date);
            }
            if (originalTimeSpan) {
                originalTimeSpan.textContent = originalSlotData.time;
            }
            if (originalCabinetSpan) {
                originalCabinetSpan.textContent = originalSlotData.cabinetName
                    ? `${originalSlotData.cabinet} (${originalSlotData.cabinetName})`
                    : originalSlotData.cabinet;
            }

            updateNextSlotInfo(currentSlotId, originalSlotData.date);
        }
    }


    // Функция для форматирования опций (опционально)
    function formatServiceOption(service) {
        if (!service.id) {
            return service.text;
        }

        // Можно добавить группировку по категориям
        const $option = $(service.element);
        const category = $option.data('category');

        if (category) {
            return $('<span><small class="text-muted">[' + category + '] </small>' + service.text + '</span>');
        }

        return service.text;
    }

    async function updateServicePricesForDate(visitDate) {
        if (!visitDate) return;

        const serviceSelect = document.getElementById('id_service');
        const additionalServiceSelect = document.getElementById('id_additional_service');

        // если на странице нет селектов — выходим
        if (!serviceSelect && !additionalServiceSelect) return;

        try {
            const response = await fetch('/appointments/api/doctor-services/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    doctor_id: doctorId,
                    date: visitDate
                })
            });

            const data = await response.json();
            if (!data.success || !data.services) return;

            const servicesMap = new Map();
            data.services.forEach(s => servicesMap.set(String(s.id), s));

            function patchSelect(selectEl) {
                if (!selectEl) return;
                const currentValue = selectEl.value;

                Array.from(selectEl.options).forEach(opt => {
                    if (!opt.value) return;
                    const s = servicesMap.get(String(opt.value));
                    if (!s) return;

                    opt.textContent = `${s.name} (${s.price} руб.)`;
                    opt.dataset.price = s.price;
                    if (s.category) opt.dataset.category = s.category;
                });

                // восстановим выбор
                selectEl.value = currentValue;
            }

            patchSelect(serviceSelect);
            patchSelect(additionalServiceSelect);

            // если у вас есть пересчёт суммы по dataset.price — можно триггернуть change
            if (serviceSelect) serviceSelect.dispatchEvent(new Event('change'));
        } catch (e) {
            // тихо, чтобы не ломать UX
        }
    }

    // Функция для форматирования выбранного элемента
    function formatServiceSelection(service) {
        return service.text;
    }
    function resetTimeSelection() {
        const allowTimeChangeInput = document.getElementById('id_allow_time_change');
        const newTimeSlotIdInput = document.getElementById('id_new_time_slot_id');
        const newAppointmentDateInput = document.getElementById('id_new_appointment_date');

        if (allowTimeChangeInput) allowTimeChangeInput.value = 'false';
        if (newTimeSlotIdInput) newTimeSlotIdInput.value = '';
        if (newAppointmentDateInput) newAppointmentDateInput.value = '';

        selectedSlot = null;

        if (timeSlotSelector) {
            const dateInput = document.getElementById('timeslot-date');
            const slotSelect = document.getElementById('timeslot-select');
            const infoDiv = document.getElementById('timeslot-info');

            if (dateInput) dateInput.value = '';
            if (slotSelect) {
                slotSelect.innerHTML = '<option value="">Сначала выберите дату</option>';
                slotSelect.disabled = true;
            }
            if (infoDiv) infoDiv.style.display = 'none';
        }
    }

    function saveSelectedTime() {
        if (!selectedSlot) return false;

        const allowTimeChangeInput = document.getElementById('id_allow_time_change');
        const newTimeSlotIdInput = document.getElementById('id_new_time_slot_id');
        const newAppointmentDateInput = document.getElementById('id_new_appointment_date');

        if (!allowTimeChangeInput || !newTimeSlotIdInput || !newAppointmentDateInput) {
            return false;
        }

        allowTimeChangeInput.value = 'true';
        newTimeSlotIdInput.value = selectedSlot.id;
        newAppointmentDateInput.value = selectedSlot.date;

        return true;
    }

    function toggleTimeChangeMode(enabled) {
        isChangingTime = enabled;

        if (enabled) {
            selectorContainer.style.display = 'block';
            originalInfo.style.display = 'none';
            timeChangeButtons.style.display = 'block';
            changeTimeBtn.innerHTML = '<i class="fas fa-times"></i> Отменить изменение';
            changeTimeBtn.classList.remove('btn-outline-warning');
            changeTimeBtn.classList.add('btn-outline-danger');

            if (confirmBtn) confirmBtn.disabled = true;
            if (cancelBtn) cancelBtn.disabled = false;

            resetTimeSelection();

            if (!timeSlotSelector) {
                timeSlotSelector = window.AppointmentUtils.TimeSlotSelector.create({
                    containerId: 'timeslot-selector-container',
                    apiUrl: availableSlotsUrl,
                    csrfToken: csrfToken,
                    doctorId: doctorId,
                    currentSlotId: currentSlotId,
                    currentAppointmentId: null,
                    initialDate: originalDate,
                    onSlotSelect: function(slotData) {
                        selectedSlot = slotData;

                        updateServicePricesForDate(slotData.date);

                        if (confirmBtn) confirmBtn.disabled = false;

                        const infoDiv = document.getElementById('timeslot-info');
                        const displaySpan = document.getElementById('timeslot-display');
                        if (infoDiv && displaySpan) {
                            displaySpan.textContent = slotData.display || 'Неизвестное время';
                            infoDiv.style.display = 'block';
                        }
                    }
                });
            }
        } else {
            selectorContainer.style.display = 'none';
            originalInfo.style.display = 'block';
            timeChangeButtons.style.display = 'none';
            changeTimeBtn.innerHTML = '<i class="fas fa-clock"></i> Изменить время';
            changeTimeBtn.classList.remove('btn-outline-danger');
            changeTimeBtn.classList.add('btn-outline-warning');
        }
    }

    changeTimeBtn.addEventListener('click', function() {
        if (!isChangingTime) {
            toggleTimeChangeMode(true);
        } else {
            toggleTimeChangeMode(false);
            updateOriginalDisplay(null);
        }
    });

    if (confirmBtn) {
        confirmBtn.addEventListener('click', function() {
            if (!isChangingTime) return;

            if (!selectedSlot || !selectedSlot.id) {
                alert('Пожалуйста, выберите временной слот');
                return;
            }

            if (!saveSelectedTime()) {
                alert('Ошибка сохранения выбранного времени');
                return;
            }

            toggleTimeChangeMode(false);
            updateOriginalDisplay(selectedSlot);
        });
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            if (!isChangingTime) return;

            toggleTimeChangeMode(false);
            updateOriginalDisplay(null);
            updateServicePricesForDate(originalSlotData.date);
        });
    }

    updateNextSlotInfo(currentSlotId, originalDate);
}
// Добавьте эту функцию после существующих функций
