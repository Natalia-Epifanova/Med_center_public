document.addEventListener('DOMContentLoaded', function() {
    // 1. Инициализация форматирования телефона
    const phoneInput = document.getElementById('id_phone_number');
    if (phoneInput && window.AppointmentUtils) {
        window.AppointmentUtils.PhoneFormatter.initialize(phoneInput);
    }

    // 2. Инициализация обновления суммы
    if (window.AppointmentUtils) {
        window.AppointmentUtils.TotalSumUpdater.initialize('id_service', 'id_total_sum');
    }

    // 3. Инициализация проверки пациента
    initializePatientChecker();

    // 4. Инициализация процедурного кабинета для ОСНОВНОЙ услуги
    if (window.AppointmentUtils) {
        window.AppointmentUtils.ProceduralManager.initialize('id_service', 'id_needs_procedural');
    }

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

    // 10. Настройка обработки ошибок сервера
    setupFormErrorHandling();
});

function setupFormErrorHandling() {
    const appointmentForm = document.getElementById('appointmentForm');
    if (!appointmentForm) return;

    // Перехватываем отправку формы для AJAX проверки
    appointmentForm.addEventListener('submit', function(e) {
        // Если уже есть обработчик в initializeChainManager, добавьте это туда
        console.log('Form submitting...');

        // Временно: отмените стандартную отправку и сделайте AJAX
        // e.preventDefault(); // РАСКОММЕНТИРУЙТЕ ЭТО ДЛЯ ТЕСТА

        // Альтернативно: добавьте кнопку для тестирования AJAX
        const testAjaxBtn = document.createElement('button');
        testAjaxBtn.type = 'button';
        testAjaxBtn.className = 'btn btn-info btn-sm mt-2';
        testAjaxBtn.textContent = 'Тест: Проверить данные AJAX';
        testAjaxBtn.addEventListener('click', testFormSubmission);

        const submitBtn = appointmentForm.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.parentNode.insertBefore(testAjaxBtn, submitBtn.nextSibling);
        }
    });
}

// Функция для тестирования AJAX отправки
async function testFormSubmission() {
    console.log('=== TEST AJAX SUBMISSION ===');

    const appointmentForm = document.getElementById('appointmentForm');
    if (!appointmentForm) return;

    const formData = new FormData(appointmentForm);

    // Преобразуем FormData в объект для отладки
    const data = {};
    for (let [key, value] of formData.entries()) {
        data[key] = value;
    }

    console.log('Form data:', data);

    try {
        const response = await fetch(window.location.href, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'  // Для определения AJAX запроса
            },
            body: formData
        });

        const responseText = await response.text();
        console.log('Response status:', response.status);
        console.log('Response text:', responseText);

        // Если есть ошибки, покажите их
        if (response.status >= 400) {
            showServerErrors([`Ошибка сервера: ${response.status}`]);
        }

        // Попробуем парсить как HTML для поиска ошибок
        const parser = new DOMParser();
        const doc = parser.parseFromString(responseText, 'text/html');

        // Ищем ошибки в ответе
        const errorList = doc.querySelector('.alert-danger ul');
        if (errorList) {
            const errors = Array.from(errorList.querySelectorAll('li')).map(li => li.textContent);
            showServerErrors(errors);
        }

    } catch (error) {
        console.error('AJAX request error:', error);
        showServerErrors([`Ошибка сети: ${error.message}`]);
    }
}

function showServerErrors(errors) {
    const container = document.getElementById('server-errors-container');
    const list = document.getElementById('server-errors-list');

    if (!container || !list) return;

    if (errors && errors.length > 0) {
        list.innerHTML = '';
        errors.forEach(error => {
            const li = document.createElement('li');
            li.textContent = error;
            list.appendChild(li);
        });
        container.style.display = 'block';

        // Прокрутить к ошибкам
        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
        container.style.display = 'none';
    }
}

function initializePatientChecker() {
    if (!window.AppointmentUtils || !window.AppointmentUtils.PatientChecker) return;

    const patientChecker = window.AppointmentUtils.PatientChecker.create({
        checkPatientUrl: checkPatientUrl,
        csrfToken: csrfToken
    });

    patientChecker.initializeCheckButton('checkPatientBtn', 'patientCheckResult');
}

function initializeAppointmentTypeManager() {
    const radios = document.querySelectorAll('input[name="appointment_chain_type"]');
    const additionalServiceSection = document.getElementById('additionalServiceSection');
    const twoSlotsSection = document.getElementById('twoSlotsSection');

    if (radios.length > 0 && additionalServiceSection && twoSlotsSection) {
        initializeAppointmentTypeManagerLegacy();
    }
}

function setupAdditionalProceduralCheckbox() {
    const additionalProceduralVisibleCheckbox = document.getElementById('needs_procedural_additional_checkbox');
    const additionalProceduralCheckbox = document.getElementById('id_needs_procedural_additional');

    if (additionalProceduralVisibleCheckbox && additionalProceduralCheckbox) {
        additionalProceduralVisibleCheckbox.addEventListener('change', function() {
            additionalProceduralCheckbox.value = this.checked ? 'true' : 'false';
        });

        additionalProceduralCheckbox.value = additionalProceduralVisibleCheckbox.checked ? 'true' : 'false';

        const appointmentForm = document.getElementById('appointmentForm');
        if (appointmentForm) {
            appointmentForm.addEventListener('submit', function() {
                additionalProceduralCheckbox.value = additionalProceduralVisibleCheckbox.checked ? 'true' : 'false';
            });
        }
    }
}

function initializeAppointmentTypeManagerLegacy() {
    const radios = document.querySelectorAll('input[name="appointment_chain_type"]');
    const additionalServiceSection = document.getElementById('additionalServiceSection');
    const additionalProceduralSection = document.getElementById('additionalServiceProceduralSection');
    const twoSlotsSection = document.getElementById('twoSlotsSection');
    const additionalServiceSelect = document.getElementById('id_additional_service');
    const mainServiceSelect = document.getElementById('id_service');
    const sameDoctorSections = document.getElementById('sameDoctorSections');

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

    function updateSectionsVisibility(value) {
        if (sameDoctorSections) sameDoctorSections.style.display = 'none';
        if (additionalServiceSection) additionalServiceSection.style.display = 'none';
        if (additionalProceduralSection) additionalProceduralSection.style.display = 'none';
        if (twoSlotsSection) twoSlotsSection.style.display = 'none';

        if (value === 'additional' || value === 'two_slots') {
            if (sameDoctorSections) sameDoctorSections.style.display = 'block';

            if (value === 'additional' && additionalServiceSection) {
                additionalServiceSection.style.display = 'block';
                populateAdditionalServices();

                if (additionalServiceSelect && additionalServiceSelect.value) {
                    additionalProceduralSection.style.display = 'block';
                }
            } else if (value === 'two_slots' && twoSlotsSection) {
                twoSlotsSection.style.display = 'block';
            }
        }
    }

    function handleAppointmentTypeChange(event) {
        updateSectionsVisibility(event.target.value);
    }

    function handleAdditionalServiceChange() {
        if (!additionalProceduralSection) return;

        if (this.value) {
            additionalProceduralSection.style.display = 'block';
        } else {
            additionalProceduralSection.style.display = 'none';

            const additionalProceduralCheckbox = document.getElementById('needs_procedural_additional_checkbox');
            if (additionalProceduralCheckbox) additionalProceduralCheckbox.checked = false;

            const hiddenField = document.getElementById('id_needs_procedural_additional');
            if (hiddenField) hiddenField.value = 'false';
        }
    }

    if (radios.length > 0) {
        radios.forEach(radio => {
            radio.addEventListener('change', handleAppointmentTypeChange);
        });

        const checkedRadio = document.querySelector('input[name="appointment_chain_type"]:checked');
        if (checkedRadio) updateSectionsVisibility(checkedRadio.value);
    }

    if (mainServiceSelect && additionalServiceSelect) {
        mainServiceSelect.addEventListener('change', () => {
            if (additionalServiceSection && additionalServiceSection.style.display === 'block') {
                populateAdditionalServices();
            }
        });
    }

    if (additionalServiceSelect) {
        additionalServiceSelect.addEventListener('change', handleAdditionalServiceChange);
    }
}

function initializeChainManager() {
    if (!window.AppointmentChainManager) return;
    if (!csrfToken || !doctorId || !originalDate) return;

    const chainManager = new AppointmentChainManager({
        csrfToken: csrfToken,
        mainDoctorId: doctorId,
        mainDate: originalDate,
        maxAdditionalAppointments: 5
    });

    const addBtn = document.getElementById('addAppointmentForm');
    if (addBtn) {
        addBtn.addEventListener('click', () => chainManager.addAppointmentForm());
    }

    const addAnotherBtn = document.getElementById('addAnotherAppointment');
    if (addAnotherBtn) {
        addAnotherBtn.addEventListener('click', () => chainManager.addAnotherDoctorForm());
    }

    const appointmentForm = document.getElementById('appointmentForm');
    if (appointmentForm) {
        // ОТЛАДКА: Добавьте обработчик перед отправкой
        appointmentForm.addEventListener('submit', function(e) {
            console.log('=== FORM SUBMIT DEBUG ===');
            console.log('Chain manager validation:', chainManager.validateBeforeSubmit());

            if (!chainManager.validateBeforeSubmit()) {
                e.preventDefault();
                return false;
            }

            chainManager.updateHiddenField();
            chainManager.updateProceduralHiddenField();

            const chainType = document.querySelector('input[name="appointment_chain_type"]:checked');
            if (chainType) {
                const value = chainType.value;
                if ((value === 'another_doctor' || value === 'multiple') &&
                    chainManager.additionalAppointments.length === 0) {
                    alert('Пожалуйста, заполните данные дополнительной записи');
                    e.preventDefault();
                    return false;
                }
            }

            // ДОБАВЬТЕ: проверить данные перед отправкой
            const hiddenField = document.getElementById('id_additional_appointments_data');
            if (hiddenField && hiddenField.value) {
                try {
                    const data = JSON.parse(hiddenField.value);
                    console.log('Additional appointments data to send:', data);
                } catch (e) {
                    console.error('Error parsing additional appointments data:', e);
                }
            }
        });
    }

    window.chainManager = chainManager;
}

function initializeProceduralManagerForAdditionalService() {
    if (!window.AppointmentUtils || !window.AppointmentUtils.ProceduralManager) return;

    const additionalServiceSelect = document.getElementById('id_additional_service');
    const additionalProceduralVisibleCheckbox = document.getElementById('needs_procedural_additional_checkbox');
    const additionalProceduralSection = document.getElementById('additionalServiceProceduralSection');
    const additionalProceduralHiddenField = document.getElementById('id_needs_procedural_additional');

    if (additionalServiceSelect && additionalProceduralVisibleCheckbox && additionalProceduralSection) {
        additionalServiceSelect.addEventListener('change', function() {
            window.AppointmentUtils.ProceduralManager.updateProceduralCheckbox(
                this,
                additionalProceduralVisibleCheckbox
            );

            if (this.value) {
                additionalProceduralSection.style.display = 'block';
                const selectedOption = this.options[this.selectedIndex];
                const serviceName = selectedOption.text.toLowerCase();

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
                    if (additionalProceduralHiddenField) {
                        additionalProceduralHiddenField.value = 'true';
                    }
                } else {
                    if (additionalProceduralVisibleCheckbox.checked) {
                        additionalProceduralVisibleCheckbox.checked = false;
                    }
                    if (additionalProceduralHiddenField) {
                        additionalProceduralHiddenField.value = 'false';
                    }
                }
            } else {
                additionalProceduralSection.style.display = 'none';
                if (additionalProceduralVisibleCheckbox.checked) {
                    additionalProceduralVisibleCheckbox.checked = false;
                }
                if (additionalProceduralHiddenField) {
                    additionalProceduralHiddenField.value = 'false';
                }
            }
        });

        if (additionalServiceSelect.value) {
            window.AppointmentUtils.ProceduralManager.updateProceduralCheckbox(
                additionalServiceSelect,
                additionalProceduralVisibleCheckbox
            );
            additionalProceduralSection.style.display = 'block';

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
        });
    }

    updateNextSlotInfo(currentSlotId, originalDate);
}