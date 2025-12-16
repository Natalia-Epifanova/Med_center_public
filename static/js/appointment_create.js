document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DEBUG: Appointment Form Loaded ===');

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

    // Автоматическая отметка процедурного кабинета для блокад
    const serviceSelect = document.getElementById('id_service');
    const needsProceduralCheckbox = document.getElementById('id_needs_procedural');

    if (serviceSelect && needsProceduralCheckbox) {
        serviceSelect.addEventListener('change', function() {
            if (window.AppointmentUtils.ServiceValidator.isMedicalBlockade(this)) {
                needsProceduralCheckbox.checked = true;
            }
        });

        // Инициализация при загрузке
        if (window.AppointmentUtils.ServiceValidator.isMedicalBlockade(serviceSelect)) {
            needsProceduralCheckbox.checked = true;
        }
    }

    // Проверка ограничений врача Пищелева
    if (serviceSelect) {
        serviceSelect.addEventListener('change', function() {
            window.AppointmentUtils.ServiceValidator.checkServiceRestrictions(this);
        });
        window.AppointmentUtils.ServiceValidator.checkServiceRestrictions(serviceSelect);
    }

    // Инициализация менеджера типов записей
    const appointmentTypeManager = window.AppointmentUtils.AppointmentTypeManager.create({
        radios: document.querySelectorAll('input[name="appointment_type"]'),
        additionalServiceSection: document.getElementById('additionalServiceSection'),
        twoSlotsSection: document.getElementById('twoSlotsSection'),
        additionalServiceSelect: document.getElementById('id_additional_service'),
        mainServiceSelect: serviceSelect
    });

    // Инициализация проверки пациента
    if (typeof checkPatientUrl !== 'undefined' && typeof csrfToken !== 'undefined') {
        const patientChecker = window.AppointmentUtils.PatientChecker.create({
            checkPatientUrl: checkPatientUrl,
            csrfToken: csrfToken
        });

        patientChecker.initializeCheckButton('checkPatientBtn', 'patientCheckResult');
    } else {
        console.warn('Patient check URL or CSRF token not defined');
    }

    // Инициализация обновления суммы
    window.AppointmentUtils.TotalSumUpdater.initialize('id_service', 'id_total_sum');

    console.log('Event listeners initialized successfully');
});