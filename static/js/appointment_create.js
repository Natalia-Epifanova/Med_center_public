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

    // 10. Инициализация валидации для Пищелева для ОСНОВНОЙ услуги
    initializePishchelevValidationForMainService();

    // 11. Настройка валидации формы перед отправкой
    setupFormValidation();

    // 12. Инициализация поиска пациента
    initializePatientSearch();


});

// НОВАЯ ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ИМЕНИ ВРАЧА
function getDoctorName() {
    // Пробуем разные способы
    if (typeof doctorName !== 'undefined' && doctorName) {
        console.log('Got doctorName from template variable:', doctorName);
        return doctorName;
    }

    // Из заголовка
    const header = document.querySelector('.card-title');
    if (header) {
        const text = header.textContent.trim();
        console.log('Got doctorName from header:', text);
        return text;
    }

    // Из информационного блока
    const infoBlock = document.querySelector('.alert-info');
    if (infoBlock) {
        const text = infoBlock.textContent;
        const doctorMatch = text.match(/Врач:\s*([^\n]+)/);
        if (doctorMatch && doctorMatch[1]) {
            console.log('Got doctorName from info block:', doctorMatch[1].trim());
            return doctorMatch[1].trim();
        }
    }

    console.error('Could not determine doctor name');
    return '';
}

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

function initializePatientSearch() {
    const searchInput = document.getElementById('patient-search-input');
    const searchBtn = document.getElementById('patient-search-btn');
    const resultsContainer = document.getElementById('patient-search-results');
    const resultsList = document.getElementById('patient-results-list');

    if (!searchInput || !searchBtn || !resultsContainer || !resultsList) return;

    async function performSearch() {
        const query = searchInput.value.trim();

        if (query.length < 2) {
            alert('Введите хотя бы 2 символа для поиска');
            return;
        }

        searchBtn.disabled = true;
        searchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        resultsList.innerHTML = '<div class="text-center py-3"><i class="fas fa-spinner fa-spin"></i> Поиск...</div>';
        resultsContainer.style.display = 'block';

        try {
            const searchUrl = "/patients/api/search-patients/";
            const response = await fetch(`${searchUrl}?q=${encodeURIComponent(query)}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            resultsList.innerHTML = '';

            if (data.error) {
                resultsList.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                return;
            }

            if (data.count === 0) {
                resultsList.innerHTML = '<div class="alert alert-info">Пациенты не найдены</div>';
                return;
            }

            data.patients.forEach(patient => {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'list-group-item list-group-item-action';

                // ОТЛАДКА: показываем все поля пациента
                console.log('Patient data from API:', patient);

                item.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${patient.full_name}</strong><br>
                            <small class="text-muted">

                                ${patient.card_number ? `Номер карты (Ревмамед): ${patient.card_number}` : 'Без карты'}
                                ${patient.date_of_birth ? ` | Дата рождения: ${patient.date_of_birth}` : ''}
                                ${patient.phone_number ? ` | Телефон: ${patient.phone_number}` : ''}
                            </small>
                        </div>
                        <button type="button" class="btn btn-sm btn-outline-primary use-patient-btn"
                                data-patient-id="${patient.id}">
                            Выбрать
                        </button>
                    </div>
                `;

                item.querySelector('.use-patient-btn').addEventListener('click', (e) => {
                    e.stopPropagation();
                    selectPatient(patient);
                });

                resultsList.appendChild(item);
            });

        } catch (error) {
            resultsList.innerHTML = `<div class="alert alert-danger">Ошибка поиска: ${error.message}</div>`;
        } finally {
            searchBtn.disabled = false;
            searchBtn.innerHTML = '<i class="fas fa-search"></i> Найти';
        }
    }

    function selectPatient(patient) {
        // 1. ИСПРАВЛЕННЫЕ ID ПОЛЕЙ - проверьте, какие ID на самом деле в вашей форме
        const fieldIds = {
            surname: 'id_surname',           // Возможно у вас 'id_lastname' или 'id_familyname'
            first_name: 'id_first_name',     // Возможно 'id_name'
            last_name: 'id_last_name',       // Возможно 'id_patronymic'
            phone_number: 'id_phone_number',
            card_number: 'id_card_number',
            date_of_birth: 'id_date_of_birth'
        };

        // 2. ПРОВЕРЬТЕ ID В БРАУЗЕРЕ
        console.log('ID проверка:', {
            fields: fieldIds,
            patient: patient
        });

        // 3. ЗАПОЛНЕНИЕ С ПРОВЕРКОЙ
        function setFieldValue(fieldId, value) {
            const field = document.getElementById(fieldId);
            if (field && value !== undefined && value !== null) {
                field.value = value;
                console.log(`Заполнено ${fieldId}: ${value}`);
            } else if (!field) {
                console.warn(`Поле не найдено: ${fieldId}`);
            }
        }

        // 4. ОСНОВНЫЕ ПОЛЯ
        setFieldValue(fieldIds.surname, patient.surname || '');
        setFieldValue(fieldIds.first_name, patient.first_name || '');
        setFieldValue(fieldIds.last_name, patient.last_name || '');

        // 5. ТЕЛЕФОН (форматирование как +7...)
        if (patient.phone_number) {
            let phone = patient.phone_number.toString();
            if (!phone.startsWith('+')) {
                if (phone.startsWith('8')) {
                    phone = '+7' + phone.slice(1);
                } else if (phone.startsWith('7')) {
                    phone = '+' + phone;
                } else {
                    phone = '+7' + phone;
                }
            }
            setFieldValue(fieldIds.phone_number, phone);
        }

        // 6. НОМЕР КАРТЫ
        setFieldValue(fieldIds.card_number, patient.card_number || '');

        // 7. ДАТА РОЖДЕНИЯ (преобразование формата DD.MM.YYYY -> YYYY-MM-DD)
        if (patient.date_of_birth) {
            try {
                const dateStr = patient.date_of_birth;
                let formattedDate = dateStr;

                // Если дата в формате DD.MM.YYYY
                if (dateStr.includes('.')) {
                    const parts = dateStr.split('.');
                    if (parts.length === 3) {
                        const [day, month, year] = parts;
                        formattedDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
                    }
                }

                setFieldValue(fieldIds.date_of_birth, formattedDate);
            } catch (e) {
                console.warn('Ошибка форматирования даты:', e);
                setFieldValue(fieldIds.date_of_birth, patient.date_of_birth);
            }
        }

        // 8. СКРЫВАЕМ РЕЗУЛЬТАТЫ ПОИСКА
        const resultsContainer = document.getElementById('patient-search-results');
        if (resultsContainer) resultsContainer.style.display = 'none';

        const searchInput = document.getElementById('patient-search-input');
        if (searchInput) searchInput.value = '';

        // 9. ПОКАЗЫВАЕМ СООБЩЕНИЕ О ВЫБОРЕ
        const resultContainer = document.getElementById('patientCheckResult');
        if (resultContainer) {
            resultContainer.innerHTML = `
                <div class="alert alert-success">
                    <i class="fas fa-check-circle"></i>
                    <strong>Пациент выбран:</strong> ${patient.full_name}
                    ${patient.card_number ? ` (Карта: ${patient.card_number})` : ''}
                </div>
            `;
            resultContainer.style.display = 'block';
        }

        // 10. АВТОМАТИЧЕСКАЯ ПРОВЕРКА (опционально)
        setTimeout(() => {
            const checkBtn = document.getElementById('checkPatientBtn');
            if (checkBtn) {
                console.log('Запускаем автоматическую проверку пациента...');
                checkBtn.click();
            }
        }, 500);
    }

    // Обработчики событий
    searchBtn.addEventListener('click', performSearch);

    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            performSearch();
        }
    });

    // Автопоиск при вводе (с задержкой)
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();

        if (query.length >= 3) {
            searchTimeout = setTimeout(performSearch, 500);
        } else {
            resultsContainer.style.display = 'none';
        }
    });

    // Клик вне результатов скрывает их
    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) &&
            !resultsContainer.contains(e.target) &&
            !searchBtn.contains(e.target)) {
            resultsContainer.style.display = 'none';
        }
    });
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
function initializePishchelevValidationForMainService() {
    console.log('=== Initializing Pishchelev validation ===');

    if (!window.AppointmentUtils || !window.AppointmentUtils.PishchelevValidator) {
        console.error('PishchelevValidator not found');
        return;
    }

    const mainServiceSelect = document.getElementById('id_service');
    if (!mainServiceSelect) {
        console.error('Main service select not found');
        return;
    }

    // Используем новую функцию для получения имени врача
    const doctorName = getDoctorName();

    if (!doctorName) {
        console.warn('Не удалось определить имя врача для валидации Пищелева');
        return;
    }

    console.log('Pishchelev validation initialized for doctor:', doctorName);

    // Инициализируем валидатор для основной услуги
    window.AppointmentUtils.PishchelevValidator.initializeForForm('id_service', doctorName);

    // Также проверяем сразу при загрузке, если услуга уже выбрана
    if (mainServiceSelect.value) {
        setTimeout(() => {
            window.AppointmentUtils.PishchelevValidator.validateServiceForPishchelev(
                mainServiceSelect, doctorName
            );
        }, 100);
    }
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

function setupFormValidation() {
    const appointmentForm = document.getElementById('appointmentForm');
    if (!appointmentForm) return;

    appointmentForm.addEventListener('submit', function(e) {
        // Проверяем валидацию Пищелева перед отправкой
        if (!validatePishchelevBeforeSubmit()) {
            e.preventDefault();
            return false;
        }

        return true;
    });
}

function validatePishchelevBeforeSubmit() {
    const mainServiceSelect = document.getElementById('id_service');
    if (!mainServiceSelect) return true;

    // Получаем имя врача
    const doctorName = getDoctorName();
    if (!doctorName) return true;

    // Получаем выбранную услугу
    const selectedOption = mainServiceSelect.options[mainServiceSelect.selectedIndex];
    if (!selectedOption || !selectedOption.value) return true;

    const serviceName = selectedOption.textContent;

    // Получаем время из страницы
    const timeText = document.querySelector('.alert-info')?.textContent || '';
    const timeTextFromHidden = document.getElementById('js-original-time')?.value || '';
    const actualTimeText = timeText || timeTextFromHidden;

    // Проверяем через валидатор
    if (window.AppointmentUtils && window.AppointmentUtils.PishchelevValidator) {
        const slotDuration = window.AppointmentUtils.PishchelevValidator.getSlotDuration(actualTimeText);

        if (slotDuration !== null) {
            const validation = window.AppointmentUtils.PishchelevValidator.validateSlotForPishchelev(
                slotDuration, serviceName, doctorName
            );

            if (!validation.valid) {
                // Показываем ошибку и блокируем отправку
                alert('❌ Ошибка!\n\n' + validation.message +
                      '\n\nИсправьте выбор услуги или времени перед сохранением.');
                return false;
            }
        }
    }

    return true;
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