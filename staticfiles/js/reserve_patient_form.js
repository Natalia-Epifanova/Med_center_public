// static/js/reserve_patient_form.js

document.addEventListener('DOMContentLoaded', function() {
    // Настройка форматирования телефона
    initializePhoneFormatting();

    // Проверка формы при отправке
    initializeFormValidation();

    // Инициализация ручного поиска (первая - как в обычной записи)
    initializePatientSearch();

    // Инициализация автопоиска пациента (вторая)
    initializeAutoPatientSearch();

    // Инициализация проверки пациента
    initializePatientCheck();
});

function initializePhoneFormatting() {
    const phoneInput = document.querySelector('[name="phone_number"]');

    if (phoneInput) {
        phoneInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/[^\d+]/g, '');

            if (!value.startsWith('+7') && value.length > 0) {
                if (value.startsWith('8')) {
                    value = '+7' + value.slice(1);
                } else if (value.startsWith('7')) {
                    value = '+' + value;
                } else {
                    value = '+7' + value;
                }
            }

            if (value.length > 12) {
                value = value.substring(0, 12);
            }

            e.target.value = value;
        });

        phoneInput.addEventListener('blur', function(e) {
            let value = e.target.value.replace(/[^\d+]/g, '');

            if (value && !value.startsWith('+7')) {
                if (value.startsWith('8')) {
                    value = '+7' + value.slice(1);
                } else if (value.startsWith('7')) {
                    value = '+' + value;
                } else if (value.length === 10) {
                    value = '+7' + value;
                }
                e.target.value = value;
            }
        });
    }
}

function initializeFormValidation() {
    const form = document.getElementById('reservePatientForm');
    const doctorSelect = document.getElementById('doctorSelect');

    if (form && doctorSelect) {
        form.addEventListener('submit', function(e) {
            const isEditMode = form.dataset.editMode === 'true';

            if (doctorSelect && !doctorSelect.value && !isEditMode) {
                e.preventDefault();
                alert('Пожалуйста, выберите врача');
                doctorSelect.focus();
                return false;
            }

            const requiredFields = ['surname', 'first_name', 'phone_number'];
            for (const fieldName of requiredFields) {
                const field = document.querySelector(`[name="${fieldName}"]`);
                if (field && !field.value.trim()) {
                    e.preventDefault();
                    alert(`Поле "${field.previousElementSibling?.textContent?.replace('*', '').trim()}" обязательно для заполнения`);
                    field.focus();
                    return false;
                }
            }
        });
    }
}

// === ГЛОБАЛЬНЫЕ ФУНКЦИИ ДЛЯ ВЫБОРА ПАЦИЕНТА ===

// Функция выбора пациента из результатов поиска
function selectPatientFromSearch(patient) {
    console.log('Пациент выбран из поиска:', patient);

    // Заполняем поля формы
    fillFormWithPatientData(patient);

    // Скрываем результаты поиска
    const resultsContainer = document.getElementById('patient-search-results');
    if (resultsContainer) resultsContainer.style.display = 'none';

    const searchInput = document.getElementById('patient-search-input');
    if (searchInput) searchInput.value = '';

    // Показываем сообщение о выборе
    const resultContainer = document.getElementById('patientCheckResult');
    if (resultContainer) {
        resultContainer.innerHTML = `
            <div class="alert alert-success">
                <i class="bi bi-check-circle"></i>
                <strong>Пациент выбран:</strong> ${patient.full_name}
                ${patient.card_number ? ` (Карта: ${patient.card_number})` : ''}
            </div>
        `;
        resultContainer.style.display = 'block';
    }

    // Показываем карточку пациента
    showPatientCard(patient);

    // Автоматическая проверка пациента
    setTimeout(() => {
        const checkBtn = document.getElementById('checkPatientBtn');
        if (checkBtn) {
            checkBtn.click();
        }
    }, 500);
}

// Функция заполнения формы данными пациента
function fillFormWithPatientData(patient) {
    const fieldIds = {
        surname: 'id_surname',
        first_name: 'id_first_name',
        last_name: 'id_last_name',
        phone_number: 'id_phone_number',
        date_of_birth: 'id_date_of_birth'
    };

    function setFieldValue(fieldId, value) {
        const field = document.getElementById(fieldId);
        if (field && value !== undefined && value !== null) {
            field.value = value;
            // Триггерим события изменения для обновления автопоиска
            field.dispatchEvent(new Event('input', { bubbles: true }));
            field.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    // Основные поля
    setFieldValue(fieldIds.surname, patient.surname || '');
    setFieldValue(fieldIds.first_name, patient.first_name || '');
    setFieldValue(fieldIds.last_name, patient.last_name || '');

    // Телефон
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

    // Дата рождения
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
                setFieldValue(fieldIds.date_of_birth, dateStr);
            }
        } catch (e) {
            console.warn('Ошибка форматирования даты:', e);
            setFieldValue(fieldIds.date_of_birth, patient.date_of_birth);
        }
    }
}

// Функция показа карточки пациента
function showPatientCard(patient) {
    const cardSection = document.getElementById('patientCardSection');
    const cardContent = document.getElementById('patientCardContent');

    if (!cardSection || !cardContent) return;

    let html = `
        <div class="row">
            <div class="col-md-6">
                <p class="mb-1"><strong>ФИО:</strong> ${patient.full_name}</p>
                ${patient.date_of_birth ? `<p class="mb-1"><strong>Дата рождения:</strong> ${patient.date_of_birth}</p>` : ''}
            </div>
            <div class="col-md-6">
                ${patient.phone_number ? `<p class="mb-1"><strong>Телефон:</strong> ${patient.phone_number}</p>` : ''}
                ${patient.card_number ? `<p class="mb-1"><strong>Номер карты:</strong> ${patient.card_number}</p>` : ''}
            </div>
        </div>
    `;

    cardContent.innerHTML = html;
    cardSection.style.display = 'block';

    // Добавляем обработчик для кнопки очистки
    const clearBtn = document.getElementById('clearPatientBtn');
    if (clearBtn) {
        clearBtn.onclick = function() {
            cardSection.style.display = 'none';
            cardContent.innerHTML = '';
            const fields = ['surname', 'first_name', 'last_name', 'phone_number', 'date_of_birth'];
            fields.forEach(field => {
                const el = document.getElementById(`id_${field}`);
                if (el) el.value = '';
            });
        };
    }
}

// === ОСНОВНАЯ ФУНКЦИЯ РУЧНОГО ПОИСКА ===
function initializePatientSearch() {
    const searchInput = document.getElementById('patient-search-input');
    const searchBtn = document.getElementById('patient-search-btn');
    const resultsContainer = document.getElementById('patient-search-results');
    const resultsList = document.getElementById('patient-results-list');

    if (!searchInput || !searchBtn || !resultsContainer || !resultsList) {
        console.log('Patient search elements not found');
        return;
    }

    console.log('initializePatientSearch called - ручной поиск');

    async function performSearch() {
        const query = searchInput.value.trim();

        if (query.length < 2) {
            alert('Введите хотя бы 2 символа для поиска');
            return;
        }

        searchBtn.disabled = true;
        searchBtn.innerHTML = '<i class="bi bi-search"></i> <span class="spinner-border spinner-border-sm" role="status"></span>';
        resultsList.innerHTML = '<div class="text-center py-3"><i class="bi bi-hourglass"></i> Поиск...</div>';
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

            // Отображаем найденных пациентов
            data.patients.forEach(patient => {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'list-group-item list-group-item-action';

                item.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${patient.full_name}</strong><br>
                            <small class="text-muted">
                                ${patient.card_number ? `Номер карты: ${patient.card_number}` : 'Без карты'}
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

                // Используем глобальную функцию selectPatientFromSearch
                item.querySelector('.use-patient-btn').addEventListener('click', (e) => {
                    e.stopPropagation();
                    selectPatientFromSearch(patient);
                });

                // Также добавляем возможность выбора по клику на всю строку
                item.addEventListener('click', (e) => {
                    if (!e.target.classList.contains('use-patient-btn')) {
                        selectPatientFromSearch(patient);
                    }
                });

                resultsList.appendChild(item);
            });

        } catch (error) {
            resultsList.innerHTML = `<div class="alert alert-danger">Ошибка поиска: ${error.message}</div>`;
        } finally {
            searchBtn.disabled = false;
            searchBtn.innerHTML = '<i class="bi bi-search"></i> Найти';
        }
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

// === ФУНКЦИЯ АВТОПОИСКА ===
function initializeAutoPatientSearch() {
    const surnameInput = document.getElementById('id_surname');
    const firstNameInput = document.getElementById('id_first_name');
    const lastNameInput = document.getElementById('id_last_name');
    const searchResults = document.getElementById('patient-search-results');
    const resultsList = document.getElementById('patient-results-list');

    if (!surnameInput || !firstNameInput || !searchResults || !resultsList) {
        console.log('Auto patient search elements not found');
        return;
    }

    console.log('initializeAutoPatientSearch called - автопоиск');

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
                    const patientFirstName = patient.first_name || '';
                    if (firstName && !patientFirstName.toLowerCase().includes(firstName.toLowerCase())) {
                        return false;
                    }

                    if (lastName && lastName.length > 0) {
                        const patientLastName = patient.last_name || '';
                        if (!patientLastName.toLowerCase().includes(lastName.toLowerCase())) {
                            return false;
                        }
                    }

                    return true;
                });
            }

            // Отображаем результаты
            displayAutoSearchResults(filteredPatients, surname, firstName, lastName);
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

    function displayAutoSearchResults(patients, surname, firstName, lastName) {
        resultsList.innerHTML = '';

        if (!patients || patients.length === 0) {
            if (surname.length > 0) {
                resultsList.innerHTML = `
                    <div class="alert alert-info">
                        <i class="bi bi-info-circle"></i>
                        Пациентов с фамилией "${surname}"${firstName ? ` и именем "${firstName}"` : ''}${lastName ? ` и отчеством "${lastName}"` : ''} не найдено.
                    </div>
                `;
            }
            return;
        }

        // Отображаем результаты
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

            // Используем глобальную функцию selectPatientFromSearch
            item.querySelector('.use-patient-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                selectPatientFromSearch(patient);
            });

            item.addEventListener('click', (e) => {
                if (!e.target.classList.contains('use-patient-btn')) {
                    selectPatientFromSearch(patient);
                }
            });

            resultsList.appendChild(item);
        });
    }

    // Обработчики событий для полей ввода
    [surnameInput, firstNameInput, lastNameInput].forEach(input => {
        if (input) {
            input.addEventListener('input', () => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(performAutoSearch, 300);
            });

            input.addEventListener('blur', () => {
                setTimeout(() => {
                    if (searchResults && !searchResults.matches(':hover')) {
                        searchResults.style.display = 'none';
                    }
                }, 200);
            });
        }
    });

    // Закрытие результатов при клике вне
    document.addEventListener('click', (e) => {
        if (searchResults && !searchResults.contains(e.target) &&
            surnameInput && !surnameInput.contains(e.target) &&
            firstNameInput && !firstNameInput.contains(e.target) &&
            lastNameInput && !lastNameInput.contains(e.target)) {
            searchResults.style.display = 'none';
        }
    });

    // Предотвращаем закрытие при клике внутри результатов
    if (searchResults) {
        searchResults.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    }

    // Вызываем поиск при загрузке, если уже есть данные в полях
    if (surnameInput.value.trim().length >= 2) {
        setTimeout(performAutoSearch, 500);
    }
}

// === ФУНКЦИЯ ПРОВЕРКИ ПАЦИЕНТА ===
function initializePatientCheck() {
    const checkPatientBtn = document.getElementById('checkPatientBtn');
    const checkResult = document.getElementById('patientCheckResult');

    if (checkPatientBtn) {
        checkPatientBtn.addEventListener('click', checkExistingPatient);
    }

    function checkExistingPatient() {
        const surname = document.querySelector('[name="surname"]').value.trim();
        const firstName = document.querySelector('[name="first_name"]').value.trim();
        const lastName = document.querySelector('[name="last_name"]').value.trim();
        const dob = document.querySelector('[name="date_of_birth"]').value;

        if (!surname || !firstName) {
            alert('Введите фамилию и имя для проверки');
            return;
        }

        checkPatientBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Проверка...';
        checkPatientBtn.disabled = true;

        fetch('/patients/api/check-patient/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                surname: surname,
                first_name: firstName,
                last_name: lastName,
                date_of_birth: dob
            })
        })
        .then(response => response.json())
        .then(data => {
            checkResult.style.display = 'block';

            if (data.exists) {
                const patient = data.patient;
                checkResult.innerHTML = `
                    <div class="alert alert-warning">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h6 class="alert-heading">
                                    <i class="bi bi-exclamation-triangle"></i> Пациент уже существует!
                                </h6>
                                <p class="mb-1"><strong>ФИО:</strong> ${patient.full_name}</p>
                                ${patient.phone_number ? `<p class="mb-1"><strong>Телефон:</strong> ${patient.phone_number}</p>` : ''}
                                ${patient.card_number ? `<p class="mb-1"><strong>Карта:</strong> ${patient.card_number}</p>` : ''}
                                ${patient.date_of_birth ? `<p class="mb-1"><strong>Дата рождения:</strong> ${patient.date_of_birth}</p>` : ''}

                            </div>
                        </div>
                    </div>
                `;


            } else {
                checkResult.innerHTML = `
                    <div class="alert alert-success">
                        <i class="bi bi-check-circle"></i>
                        <strong>Пациент не найден в базе.</strong> Будет создана новая запись.
                    </div>
                `;
            }
        })
        .catch(error => {
            checkResult.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    Ошибка при проверке: ${error.message}
                </div>
            `;
        })
        .finally(() => {
            checkPatientBtn.innerHTML = '<i class="bi bi-person-check"></i> Проверить по заполненным данным';
            checkPatientBtn.disabled = false;
        });
    }
}

// === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}