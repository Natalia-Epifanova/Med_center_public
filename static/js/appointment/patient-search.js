function initializeBlacklistChecker() {
    if (!window.AppointmentUtils || typeof checkBlacklistUrl === 'undefined' || !checkBlacklistUrl || !csrfToken) {
        return null;
    }

    const checker = window.AppointmentUtils.BlacklistChecker.create({
        checkBlacklistUrl: checkBlacklistUrl,
        csrfToken: csrfToken,
        resultContainerId: 'patientCheckResult',
        warningContainerId: 'patientBlacklistWarning'
    });

    checker.initialize();
    window.currentAppointmentBlacklistChecker = checker;
    return checker;
}

function triggerBlacklistCheck() {
    if (
        window.currentAppointmentBlacklistChecker &&
        typeof window.currentAppointmentBlacklistChecker.checkCurrentPatient === 'function'
    ) {
        window.currentAppointmentBlacklistChecker.checkCurrentPatient();
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
