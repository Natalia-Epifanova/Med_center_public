// static/js/reserve_patient_form.js

document.addEventListener('DOMContentLoaded', function() {
    // Настройка форматирования телефона
    initializePhoneFormatting();

    // Проверка формы при отправке
    initializeFormValidation();

    // Инициализация автопоиска пациента
    initializeAutoPatientSearch();

    // Инициализация ручного поиска
    initializeManualPatientSearch();

    // Инициализация проверки пациента
    initializePatientCheck();
});

function initializePhoneFormatting() {
    const phoneInput = document.querySelector('[name="phone_number"]');

    if (phoneInput) {
        // Автоматическое добавление +7
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

            // Ограничиваем длину
            if (value.length > 12) {
                value = value.substring(0, 12);
            }

            e.target.value = value;
        });

        // Проверка при потере фокуса
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

            // Проверяем обязательные поля
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

function initializeAutoPatientSearch() {
    const surnameInput = document.getElementById('id_surname');
    const firstNameInput = document.getElementById('id_first_name');
    const lastNameInput = document.getElementById('id_last_name');
    const searchResults = document.getElementById('patient-search-results');
    const resultsList = document.getElementById('patient-results-list');

    // Проверяем, что мы в режиме создания (не редактирования)
    const form = document.getElementById('reservePatientForm');
    if (!form || !surnameInput || !firstNameInput || !searchResults || !resultsList) {
        return;
    }

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
                        <i class="bi bi-info-circle"></i>
                        Пациентов с фамилией "${surname}"${firstName ? ` и именем "${firstName}"` : ''}${lastName ? ` и отчеством "${lastName}"` : ''} не найдено.
                    </div>
                `;
            }
            return;
        }

        patients.forEach(patient => {
            const item = document.createElement('div');
            item.className = 'list-group-item list-group-item-action';
            item.style.cursor = 'pointer';

            item.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <strong>${patient.full_name}</strong>
                        ${patient.date_of_birth ? `<div class="text-muted small">${patient.date_of_birth}</div>` : ''}
                        ${patient.phone_number ? `<div class="small"><i class="bi bi-telephone"></i> ${patient.phone_number}</div>` : ''}
                        ${patient.card_number ? `<div class="small"><i class="bi bi-card-text"></i> Карта: ${patient.card_number}</div>` : ''}
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-primary select-patient-btn"
                            data-patient-id="${patient.id}"
                            data-patient-data='${JSON.stringify(patient)}'>
                        <i class="bi bi-check-lg"></i> Выбрать
                    </button>
                </div>
            `;

            // Обработчик для кнопки выбора
            item.querySelector('.select-patient-btn').addEventListener('click', function(e) {
                e.stopPropagation();
                const patientData = JSON.parse(this.getAttribute('data-patient-data'));
                selectPatient(patientData);
            });

            // Обработчик клика на всю строку
            item.addEventListener('click', function(e) {
                if (!e.target.classList.contains('select-patient-btn')) {
                    const btn = this.querySelector('.select-patient-btn');
                    const patientData = JSON.parse(btn.getAttribute('data-patient-data'));
                    selectPatient(patientData);
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

function initializeManualPatientSearch() {
    const searchInput = document.getElementById('patient-search-input');
    const searchBtn = document.getElementById('patient-search-btn');
    const searchResults = document.getElementById('patient-search-results');
    const resultsList = document.getElementById('patient-results-list');

    if (searchBtn && searchInput) {
        searchBtn.addEventListener('click', searchPatients);
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchPatients();
            }
        });
    }

    function searchPatients() {
        const query = searchInput.value.trim();

        if (!query || query.length < 2) {
            alert('Введите хотя бы 2 символа для поиска');
            return;
        }

        // Показываем индикатор загрузки
        searchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Поиск...';
        searchBtn.disabled = true;

        // Очищаем предыдущие результаты
        resultsList.innerHTML = '';
        searchResults.style.display = 'block';

        // Отправляем запрос на поиск
        fetch(`/patients/api/search-patients/?q=${encodeURIComponent(query)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Ошибка поиска');
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    resultsList.innerHTML = `
                        <div class="list-group-item text-danger">
                            <i class="bi bi-exclamation-triangle"></i> ${data.error}
                        </div>
                    `;
                    return;
                }

                if (data.count === 0) {
                    resultsList.innerHTML = `
                        <div class="list-group-item text-muted">
                            <i class="bi bi-info-circle"></i> Пациенты не найдены
                        </div>
                    `;
                    return;
                }

                // Отображаем найденных пациентов
                data.patients.forEach(patient => {
                    const item = document.createElement('div');
                    item.className = 'list-group-item list-group-item-action';
                    item.innerHTML = `
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <strong>${patient.full_name}</strong>
                                ${patient.date_of_birth ? `<div class="text-muted small">${patient.date_of_birth}</div>` : ''}
                                ${patient.phone_number ? `<div class="small"><i class="bi bi-telephone"></i> ${patient.phone_number}</div>` : ''}
                                ${patient.card_number ? `<div class="small"><i class="bi bi-card-text"></i> Карта: ${patient.card_number}</div>` : ''}
                            </div>
                            <button type="button" class="btn btn-sm btn-outline-primary select-patient-btn"
                                    data-patient-id="${patient.id}"
                                    data-patient-data='${JSON.stringify(patient)}'>
                                <i class="bi bi-check-lg"></i> Выбрать
                            </button>
                        </div>
                    `;
                    resultsList.appendChild(item);
                });

                // Добавляем обработчики для кнопок выбора
                document.querySelectorAll('.select-patient-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const patientData = JSON.parse(this.getAttribute('data-patient-data'));
                        fillFormWithPatientData(patientData);
                        searchResults.style.display = 'none';
                        searchInput.value = '';
                    });
                });
            })
            .catch(error => {
                resultsList.innerHTML = `
                    <div class="list-group-item text-danger">
                        <i class="bi bi-exclamation-triangle"></i> Ошибка при поиске: ${error.message}
                    </div>
                `;
            })
            .finally(() => {
                searchBtn.innerHTML = '<i class="bi bi-search"></i> Найти';
                searchBtn.disabled = false;
            });
    }
}

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
                                <p class="mb-0 mt-2">
                                    <button type="button" class="btn btn-sm btn-warning" id="useExistingPatientBtn">
                                        Использовать этого пациента
                                    </button>
                                </p>
                            </div>
                        </div>
                    </div>
                `;

                // Добавляем обработчик для кнопки
                document.getElementById('useExistingPatientBtn').addEventListener('click', function() {
                    fillFormWithPatientData(patient);
                    checkResult.style.display = 'none';
                });
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

// Общие функции для всех форм
function selectPatient(patient) {
    fillFormWithPatientData(patient);
    showPatientCard(patient);

    // Скрываем результаты поиска
    const searchResults = document.getElementById('patient-search-results');
    if (searchResults) searchResults.style.display = 'none';

    // Показываем сообщение о выборе
    const resultContainer = document.getElementById('patientCheckResult');
    if (resultContainer) {
        resultContainer.innerHTML = `
            <div class="alert alert-success">
                <i class="bi bi-check-circle"></i>
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
            checkBtn.click();
        }
    }, 500);
}

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
            // Очищаем только поля пациента
            const fields = ['surname', 'first_name', 'last_name', 'phone_number', 'date_of_birth'];
            fields.forEach(field => {
                const el = document.getElementById(`id_${field}`);
                if (el) el.value = '';
            });
        };
    }
}

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