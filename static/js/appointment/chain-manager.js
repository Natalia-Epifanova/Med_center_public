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

                                ${patient.card_number ? `Номер карты (клиника): ${patient.card_number}` : 'Без карты'}
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


        // 8. ДАТА РОЖДЕНИЯ - только если пустая в форме
        const currentDobField = document.getElementById('id_date_of_birth');
        if (patient.date_of_birth && (!currentDobField || !currentDobField.value)) {
            // Заполняем только если поле пустое
            setFieldValue(fieldIds.date_of_birth, patient.date_of_birth);
        } else if (currentDobField && currentDobField.value && !patient.date_of_birth) {
            // Если у пациента нет даты рождения, но мы ввели её вручную -
            // оставляем введенное значение (будет обновлено в существующем пациенте)
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
                triggerBlacklistCheck();
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

// Добавьте эту функцию в ваш appointment_create.js
function initializeAutoPatientSearch() {
    const surnameInput = document.getElementById('id_surname');
    const firstNameInput = document.getElementById('id_first_name');
    const lastNameInput = document.getElementById('id_last_name');
    const searchResults = document.getElementById('patient-search-results');
    const resultsList = document.getElementById('patient-results-list');

    if (!surnameInput || !firstNameInput || !searchResults || !resultsList) return;

    let searchTimeout;
    let lastSearchData = {
        surname: '',
        firstName: '',
        lastName: ''
    };

    async function performAutoSearch() {
        const surname = surnameInput.value.trim();
        const firstName = firstNameInput.value.trim();
        const lastName = lastNameInput.value.trim();

        // Ищем только если есть хотя бы 2 символа в фамилии
        if (surname.length < 2) {
            if (searchResults.style.display === 'block') {
                searchResults.style.display = 'none';
            }
            return;
        }

        // Проверяем, изменились ли данные
        if (surname === lastSearchData.surname &&
            firstName === lastSearchData.firstName &&
            lastName === lastSearchData.lastName &&
            searchResults.style.display === 'block') {
            return;
        }

        lastSearchData = { surname, firstName, lastName };

        try {
            // Ищем только по фамилии - это даст больше результатов
            const searchUrl = "/patients/api/search-patients/";
            const response = await fetch(`${searchUrl}?q=${encodeURIComponent(surname)}`);

            if (!response.ok) return;

            const data = await response.json();

            if (data.error) {
                if (searchResults.style.display === 'block') {
                    searchResults.style.display = 'none';
                }
                return;
            }

            // Фильтруем результаты локально по имени и отчеству
            let filteredPatients = data.patients || [];

            if (data.count > 0 && filteredPatients.length > 0) {
                filteredPatients = filteredPatients.filter(patient => {
                    // Проверяем совпадение имени (регистронезависимо)
                    const patientFirstName = patient.first_name || '';
                    if (!patientFirstName.toLowerCase().includes(firstName.toLowerCase())) {
                        return false;
                    }

                    // Если введено отчество, проверяем его
                    if (lastName && lastName.length > 0) {
                        const patientLastName = patient.last_name || '';
                        if (!patientLastName.toLowerCase().includes(lastName.toLowerCase())) {
                            return false;
                        }
                    }

                    return true;
                });
            }

            // Всегда показываем результаты (даже если пустые)
            displaySearchResults(filteredPatients);
            if (filteredPatients.length > 0 || surname.length > 0) {
                searchResults.style.display = 'block';
            }

        } catch (error) {
            console.log('Auto-search error:', error);
            if (searchResults.style.display === 'block') {
                searchResults.style.display = 'none';
            }
        }
    }

    function displaySearchResults(patients) {
        resultsList.innerHTML = '';

        if (!patients || patients.length === 0) {
            const surname = surnameInput.value.trim();
            const firstName = firstNameInput.value.trim();
            const lastName = lastNameInput.value.trim();

            if (surname.length > 0) {
                resultsList.innerHTML = `
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle"></i>
                        Пациентов с фамилией "${surname}"${firstName ? ` и именем "${firstName}"` : ''}${lastName ? ` и отчеством "${lastName}"` : ''} не найдено.
                    </div>
                `;
            }
            return;
        }

        patients.forEach(patient => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'list-group-item list-group-item-action';

            item.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${patient.full_name}</strong><br>
                        <small class="text-muted">
                            ${patient.card_number ? `Карта: ${patient.card_number}` : 'Без карты'}
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

            // Можно также добавить возможность выбора по клику на всю строку
            item.addEventListener('click', (e) => {
                if (!e.target.classList.contains('use-patient-btn')) {
                    selectPatient(patient);
                }
            });

            resultsList.appendChild(item);
        });
    }

    function selectPatient(patient) {
        // Автоматически заполняем данные пациента
        fillPatientData(patient);

        // Скрываем результаты поиска
        searchResults.style.display = 'none';

        // Показываем сообщение о выборе
        const resultContainer = document.getElementById('patientCheckResult');
        if (resultContainer) {
            resultContainer.innerHTML = `
                <div class="alert alert-success">
                    <i class="fas fa-check-circle"></i>
                    <strong>Данные пациента заполнены:</strong> ${patient.full_name}
                    ${patient.card_number ? ` (Карта: ${patient.card_number})` : ''}
                </div>
            `;
            resultContainer.style.display = 'block';
        }

        // Автоматическая проверка пациента
        setTimeout(() => {
            const checkBtn = document.getElementById('checkPatientBtn');
            if (checkBtn) {
                console.log('Запускаем автоматическую проверку пациента...');
                checkBtn.click();
                triggerBlacklistCheck();
            }
        }, 500);
    }

    function fillPatientData(patient) {
        const fieldIds = {
            surname: 'id_surname',
            first_name: 'id_first_name',
            last_name: 'id_last_name',
            phone_number: 'id_phone_number',
            card_number: 'id_card_number',
            date_of_birth: 'id_date_of_birth'
        };

        function setFieldValue(fieldId, value) {
            const field = document.getElementById(fieldId);
            if (field && value !== undefined && value !== null) {
                field.value = value;
                // Вызываем событие input для обновления валидации
                field.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }

        // Основные поля
        setFieldValue(fieldIds.surname, patient.surname || '');
        setFieldValue(fieldIds.first_name, patient.first_name || '');
        setFieldValue(fieldIds.last_name, patient.last_name || '');

        // Телефон (форматирование как +7...)
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

        // Номер карты
        setFieldValue(fieldIds.card_number, patient.card_number || '');

        // Дата рождения (преобразование формата DD.MM.YYYY -> YYYY-MM-DD)
        if (patient.date_of_birth) {
            try {
                const dateStr = patient.date_of_birth;
                if (dateStr.includes('.')) {
                    const parts = dateStr.split('.');
                    if (parts.length === 3) {
                        const [day, month, year] = parts;
                        const formattedDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
                        setFieldValue(fieldIds.date_of_birth, formattedDate);
                    }
                } else {
                    // Если дата уже в формате YYYY-MM-DD
                    setFieldValue(fieldIds.date_of_birth, dateStr);
                }
            } catch (e) {
                console.warn('Ошибка форматирования даты:', e);
                setFieldValue(fieldIds.date_of_birth, patient.date_of_birth);
            }
        }
    }

    // Обработчики событий для полей ввода
    [surnameInput, firstNameInput, lastNameInput].forEach(input => {
        input.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(performAutoSearch, 300);
        });

        input.addEventListener('blur', () => {
            setTimeout(() => {
                if (!searchResults.matches(':hover')) {
                    searchResults.style.display = 'none';
                }
            }, 200);
        });
    });

    // Закрытие результатов при клике вне
    document.addEventListener('click', (e) => {
        if (!searchResults.contains(e.target) &&
            !surnameInput.contains(e.target) &&
            !firstNameInput.contains(e.target) &&
            !lastNameInput.contains(e.target)) {
            searchResults.style.display = 'none';
        }
    });

    // Предотвращаем закрытие при клике внутри результатов
    searchResults.addEventListener('click', (e) => {
        e.stopPropagation();
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

        // ИСПРАВЬТЕ: Также скрываем секции для других врачей
        const anotherDoctorSection = document.getElementById('anotherDoctorSection');
        const multipleSection = document.getElementById('multipleAppointmentsSection');

        if (anotherDoctorSection) anotherDoctorSection.style.display = 'none';
        if (multipleSection) multipleSection.style.display = 'none';

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
        } else if (value === 'another_doctor') {
            if (anotherDoctorSection) anotherDoctorSection.style.display = 'block';
        } else if (value === 'multiple') {
            if (multipleSection) multipleSection.style.display = 'block';
        }
    }

    function handleAppointmentTypeChange(event) {
        updateSectionsVisibility(event.target.value);

        // ИСПРАВЬТЕ: Также вызываем метод цепочки
        if (window.chainManager) {
            window.chainManager.onChainTypeChange(event.target.value);
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
function handleAdditionalServiceChange(event) {
    const additionalProceduralSection = document.getElementById('additionalServiceProceduralSection');
    const additionalProceduralVisibleCheckbox = document.getElementById('needs_procedural_additional_checkbox');
    const additionalServiceSelect = event.target;

    if (!additionalProceduralSection || !additionalProceduralVisibleCheckbox) return;

    // Показываем/скрываем секцию процедурного кабинета для дополнительной услуги
    if (additionalServiceSelect.value) {
        additionalProceduralSection.style.display = 'block';

        // Автоматически отмечаем процедурный кабинет для определенных услуг
        const selectedOption = additionalServiceSelect.options[additionalServiceSelect.selectedIndex];
        const serviceName = selectedOption.text.toLowerCase();

        const needsProcedural = serviceName.includes('блокада') ||
                               serviceName.includes('укол') ||
                               serviceName.includes('пункция') ||
                               serviceName.includes('введение') ||
                               serviceName.includes('инъекция') ||
                               serviceName.includes('внутримышечно') ||
                               serviceName.includes('внутрикожно') ||
                               serviceName.includes('внутривенно');

        if (needsProcedural && !additionalProceduralVisibleCheckbox.checked) {
            additionalProceduralVisibleCheckbox.checked = true;

            // Обновляем скрытое поле
            const hiddenField = document.getElementById('id_needs_procedural_additional');
            if (hiddenField) {
                hiddenField.value = 'true';
            }
        } else if (!needsProcedural && additionalProceduralVisibleCheckbox.checked) {
            additionalProceduralVisibleCheckbox.checked = false;

            // Обновляем скрытое поле
            const hiddenField = document.getElementById('id_needs_procedural_additional');
            if (hiddenField) {
                hiddenField.value = 'false';
            }
        }
    } else {
        additionalProceduralSection.style.display = 'none';
        if (additionalProceduralVisibleCheckbox.checked) {
            additionalProceduralVisibleCheckbox.checked = false;

            // Обновляем скрытое поле
            const hiddenField = document.getElementById('id_needs_procedural_additional');
            if (hiddenField) {
                hiddenField.value = 'false';
            }
        }
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

function setupCleanupBeforeSubmit() {
    const appointmentForm = document.getElementById('appointmentForm');
    if (!appointmentForm) return;

    appointmentForm.addEventListener('submit', function() {
        // Задержка для того, чтобы chainManager успел обновиться
        setTimeout(() => {
            if (window.chainManager) {
                const chainTypeElement = document.querySelector('input[name="appointment_chain_type"]:checked');
                if (chainTypeElement) {
                    const chainType = chainTypeElement.value;

                    // Очищаем hidden поле если тип не требует дополнительных записей
                    const hiddenField = document.getElementById('id_additional_appointments_data');
                    if (hiddenField) {
                        if (chainType === 'single' || chainType === 'additional' || chainType === 'two_slots') {
                            hiddenField.value = '';
                        }
                    }
                }
            }
        }, 100);
    });
}
function setupFormValidation() {
    const appointmentForm = document.getElementById('appointmentForm');
    if (!appointmentForm) return;

    appointmentForm.addEventListener('submit', function(e) {
        if (appointmentForm.dataset.isSubmitting === 'true') {
            e.preventDefault();
            return false;
        }

        console.log('=== FORM SUBMIT DEBUG ===');

        // Проверяем валидацию Пищелева перед отправкой
        if (!validatePishchelevBeforeSubmit()) {
            e.preventDefault();
            return false;
        }

        // ВАЖНО: Очищаем пустые данные перед отправкой
        if (window.chainManager) {
            // Проверяем тип записи
            const chainTypeElement = document.querySelector('input[name="appointment_chain_type"]:checked');
            if (chainTypeElement) {
                const chainType = chainTypeElement.value;

                if (chainType === 'multiple') {
                    // Для "multiple" удаляем форму "single" если она пустая
                    const singleForm = document.querySelector('[data-form-index="single"]');
                    if (singleForm) {
                        const formData = window.chainManager.getFormData('single');
                        if (!formData || !formData.doctor_id || !formData.service_id || !formData.time_slot_id) {
                            // Форма "single" пустая - удаляем
                            window.chainManager.removeSingleFormIfExists();
                        }
                    }
                } else if (chainType === 'another_doctor') {
                    // Для "another_doctor" удаляем все формы "multiple"
                    window.chainManager.removeAllMultipleForms();
                }
            }

            // Обновляем скрытые поля
            window.chainManager.updateHiddenField();
            window.chainManager.updateProceduralHiddenField();
        }

        appointmentForm.dataset.isSubmitting = 'true';

        const submitBtn = appointmentForm.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.dataset.originalHtml = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Сохраняем...';
        }

        return true;
    });
}
