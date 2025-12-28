document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DEBUG: Procedural Appointment Form with Chains Loaded ===');
    console.log('Doctor ID for chains:', doctorId);
    console.log('Selected date:', selectedDate);

    // 1. Инициализация базовых утилит
    if (window.AppointmentUtils) {
        // Форматирование телефона
        const phoneInput = document.getElementById('id_phone_number');
        if (phoneInput) {
            window.AppointmentUtils.PhoneFormatter.initialize(phoneInput);
        }

        // Обновление суммы
        window.AppointmentUtils.TotalSumUpdater.initialize('id_service', 'id_total_sum');
    }

    // 2. Инициализация проверки пациента
    if (checkPatientUrl && csrfToken) {
        const patientChecker = window.AppointmentUtils.PatientChecker.create({
            checkPatientUrl: checkPatientUrl,
            csrfToken: csrfToken
        });
        patientChecker.initializeCheckButton('checkPatientBtn', 'patientCheckResult');

        // ДОБАВИТЬ ИНИЦИАЛИЗАЦИЮ ПОИСКА ПАЦИЕНТА
        initializePatientSearch();
    }

    // 3. Инициализация выбора анализов крови
    if (typeof BloodTestSelection !== 'undefined') {
        window.bloodTestSelection = new BloodTestSelection({
            initialTests: initialTestIds
        });

        // Показываем/скрываем блок анализов в зависимости от выбранной услуги
        const serviceSelect = document.getElementById('id_service');
        const bloodTestSection = document.getElementById('bloodTestSelectionSection');

        if (serviceSelect && bloodTestSection) {
            const toggleBloodTestSection = () => {
                const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
                const isBloodTest = selectedOption &&
                    selectedOption.text.toLowerCase().includes('забор крови');

                bloodTestSection.style.display = isBloodTest ? 'block' : 'none';

                // Если выбрана услуга забора крови, обновляем сумму
                if (isBloodTest && window.bloodTestSelection) {
                    window.bloodTestSelection.updateTotalSum();
                }
            };

            serviceSelect.addEventListener('change', toggleBloodTestSection);
            toggleBloodTestSection(); // Инициализация
        }
    }

    // 4. Инициализация менеджера цепочек записей (только если есть doctorId)
    if (typeof AppointmentChainManager !== 'undefined' && csrfToken && doctorId) {
        try {
            window.chainManager = new AppointmentChainManager({
                csrfToken: csrfToken,
                mainDoctorId: doctorId,
                mainDate: selectedDate,
                maxAdditionalAppointments: 5,
                isProcedural: true
            });

            console.log('Chain manager initialized successfully');

            // Настройка обработчиков для цепочек
            const addBtn = document.getElementById('addAppointmentForm');
            if (addBtn) {
                addBtn.addEventListener('click', () => window.chainManager.addAppointmentForm());
            }

            // Инициализация менеджера типа записи
            const initializeAppointmentTypeManager = () => {
                const radios = document.querySelectorAll('input[name="appointment_chain_type"]');
                if (radios.length === 0) return;

                const sections = {
                    sameDoctorSections: document.getElementById('sameDoctorSections'),
                    additionalServiceSection: document.getElementById('additionalServiceSection'),
                    twoSlotsSection: document.getElementById('twoSlotsSection'),
                    anotherDoctorSection: document.getElementById('anotherDoctorSection'),
                    multipleAppointmentsSection: document.getElementById('multipleAppointmentsSection')
                };

                function updateSectionsVisibility(value) {
                    // Скрываем все секции
                    Object.values(sections).forEach(section => {
                        if (section) section.style.display = 'none';
                    });

                    // Показываем нужные секции (только для процедурной формы)
                    switch(value) {
                        case 'another_doctor':
                            if (sections.anotherDoctorSection) sections.anotherDoctorSection.style.display = 'block';
                            break;

                        case 'multiple':
                            if (sections.multipleAppointmentsSection) sections.multipleAppointmentsSection.style.display = 'block';
                            break;
                    }
                }

                function handleAppointmentTypeChange(event) {
                    updateSectionsVisibility(event.target.value);
                }

                // Добавляем обработчики
                radios.forEach(radio => {
                    radio.addEventListener('change', handleAppointmentTypeChange);
                });

                // Устанавливаем начальное состояние
                const checkedRadio = document.querySelector('input[name="appointment_chain_type"]:checked');
                if (checkedRadio) {
                    updateSectionsVisibility(checkedRadio.value);
                }
            };

            initializeAppointmentTypeManager();

        } catch (error) {
            console.error('Error initializing chain manager:', error);
        }
    } else {
        console.warn('Chain manager not initialized. Missing:', {
            AppointmentChainManager: typeof AppointmentChainManager,
            csrfToken: !!csrfToken,
            doctorId: doctorId
        });
    }

    // 5. Обработчик отправки формы
    const appointmentForm = document.getElementById('appointmentForm');
    if (appointmentForm) {
        appointmentForm.addEventListener('submit', function(e) {
            console.log('Form submission started...');

            // Обновляем все скрытые поля перед отправкой
            if (window.bloodTestSelection) {
                window.bloodTestSelection.updateFormField();
                window.bloodTestSelection.updateTotalSum();
                console.log('Blood tests updated');
            }

            if (window.chainManager) {
                window.chainManager.updateHiddenField();
                window.chainManager.updateProceduralHiddenField();
                console.log('Chain data updated');

                // Валидация цепочек перед отправкой
                if (!window.chainManager.validateBeforeSubmit()) {
                    e.preventDefault();
                    return false;
                }
            }

            console.log('Form submitting...');
        });
    }
});

// ДОБАВИТЬ ФУНКЦИЮ ПОИСКА ПАЦИЕНТА (скопировать из appointment_create.js)
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
        // ID полей в процедурной форме (должны совпадать с вашей формой)
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
                console.log(`Заполнено ${fieldId}: ${value}`);
            }
        }

        // Заполняем поля
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

        // Номер карты
        setFieldValue(fieldIds.card_number, patient.card_number || '');

        // Дата рождения
        if (patient.date_of_birth) {
            try {
                const dateStr = patient.date_of_birth;
                let formattedDate = dateStr;

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
                    <i class="fas fa-check-circle"></i>
                    <strong>Пациент выбран:</strong> ${patient.full_name}
                    ${patient.card_number ? ` (Карта: ${patient.card_number})` : ''}
                </div>
            `;
            resultContainer.style.display = 'block';
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

    // Автопоиск
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