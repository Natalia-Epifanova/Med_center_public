document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DEBUG: Procedural Appointment Form Loaded ===');
    console.log('Initial test IDs:', initialTestIds);

    // Проверяем, что утилиты загружены
    if (!window.AppointmentUtils) {
        console.error('AppointmentUtils не загружен');
        return;
    }

    // Инициализация форматирования телефона
    const phoneInput = document.getElementById('id_phone_number');
    if (phoneInput) {
        window.AppointmentUtils.PhoneFormatter.initialize(phoneInput);
    }

    // Инициализация менеджера типов записей (если есть такие поля в форме)
    const appointmentTypeRadios = document.querySelectorAll('input[name="appointment_type"]');
    if (appointmentTypeRadios.length > 0) {
        const appointmentTypeManager = window.AppointmentUtils.AppointmentTypeManager.create({
            radios: appointmentTypeRadios,
            additionalServiceSection: document.getElementById('additionalServiceSection'),
            twoSlotsSection: document.getElementById('twoSlotsSection'),
            additionalServiceSelect: document.getElementById('id_additional_service'),
            mainServiceSelect: document.getElementById('id_service')
        });
    }

    // Инициализация проверки пациента
    if (typeof checkPatientUrl !== 'undefined' && typeof csrfToken !== 'undefined') {
        const patientChecker = window.AppointmentUtils.PatientChecker.create({
            checkPatientUrl: checkPatientUrl,
            csrfToken: csrfToken
        });

        patientChecker.initializeCheckButton('checkPatientBtn', 'patientCheckResult');
    }

    // Убеждаемся, что скрытые поля существуют
    const ensureHiddenFields = () => {
        const form = document.getElementById('appointmentForm');
        if (!form) return;

        if (!document.getElementById('id_selected_blood_tests')) {
            const hiddenField = document.createElement('input');
            hiddenField.type = 'hidden';
            hiddenField.id = 'id_selected_blood_tests';
            hiddenField.name = 'selected_blood_tests_input';
            form.appendChild(hiddenField);
        }

        if (!document.getElementById('id_total_sum')) {
            const hiddenField = document.createElement('input');
            hiddenField.type = 'hidden';
            hiddenField.id = 'id_total_sum';
            hiddenField.name = 'total_sum';
            form.appendChild(hiddenField);
        }
    };

    ensureHiddenFields();

    // Инициализация BloodTestSelection (оставляем как есть, т.к. специфично)
    const bloodTestSection = document.getElementById('bloodTestSelectionSection');
    if (bloodTestSection && window.BloodTestSelection) {
        console.log('Initializing BloodTestSelection with tests:', initialTestIds);

        window.bloodTestSelection = new BloodTestSelection({
            initialTests: initialTestIds
        });

        const serviceSelect = document.getElementById('id_service');
        if (serviceSelect) {
            const toggleBloodTestSection = () => {
                const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
                const isBloodTest = selectedOption &&
                    selectedOption.text.toLowerCase().includes('забор крови');

                if (bloodTestSection) {
                    bloodTestSection.style.display = isBloodTest ? 'block' : 'none';
                }
            };

            serviceSelect.addEventListener('change', toggleBloodTestSection);
            toggleBloodTestSection();
        }
    }

    // Функция обновления суммы для процедурной записи
    function updateTotalSum(customSum = null) {
        const totalField = document.getElementById('id_total_sum');
        if (!totalField) return;

        if (customSum !== null) {
            totalField.value = customSum.toFixed(2);
        } else {
            // Считаем сумму анализов + услугу
            let total = 0;

            // Сумма анализов
            if (window.bloodTestSelection) {
                window.bloodTestSelection.selectedTests.forEach(testId => {
                    const test = window.bloodTestSelection.allTests.find(t => t.id === testId);
                    if (test && test.price) {
                        total += test.price;
                    }
                });
            }

            // Добавляем стоимость услуги
            const serviceSelect = document.getElementById('id_service');
            if (serviceSelect && serviceSelect.value) {
                const servicePrice = 150; // Цена забора крови
                total += servicePrice;
            }

            totalField.value = total.toFixed(2);
        }

        console.log('Total sum updated:', totalField.value);
    }

    // Слушаем изменения в выбранных анализах
    document.addEventListener('bloodTestsUpdated', function() {
        updateTotalSum();
    });

    // Обработчик отправки формы
    const appointmentForm = document.getElementById('appointmentForm');
    if (appointmentForm) {
        appointmentForm.addEventListener('submit', function(e) {
            // Обновляем оба скрытых поля перед отправкой
            if (window.bloodTestSelection) {
                window.bloodTestSelection.updateFormField();
                updateTotalSum(); // Убедимся, что сумма обновлена

                console.log('Form submit - tests:', document.getElementById('id_selected_blood_tests').value);
                console.log('Form submit - total:', document.getElementById('id_total_sum').value);
            }
        });
    }

    console.log('Procedural appointment event listeners initialized successfully');
});