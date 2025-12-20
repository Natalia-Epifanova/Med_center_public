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