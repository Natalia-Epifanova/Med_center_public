document.addEventListener('DOMContentLoaded', function() {
    const phoneInput = document.getElementById('id_phone_number');
    if (phoneInput && window.AppointmentUtils) {
        window.AppointmentUtils.PhoneFormatter.initialize(phoneInput);
    }

    if (window.AppointmentUtils) {
        window.AppointmentUtils.TotalSumUpdater.initialize('id_service', 'id_total_sum');
    }

    initializePatientChecker();
    initializeBlacklistChecker();
    initializeServiceSearch();

    if (window.AppointmentUtils) {
        window.AppointmentUtils.ProceduralManager.initialize('id_service', 'id_needs_procedural');
    }

    initializeProceduralManagerForAdditionalService();
    initializeChainManager();
    initializeTimeSlotSelector();
    initializeAppointmentTypeManager();
    setupAdditionalProceduralCheckbox();
    initializePishchelevValidationForMainService();
    setupFormValidation();
    initializePatientSearch();
    setupCleanupBeforeSubmit();
    initializeAutoPatientSearch();
    initializeBloodTestSelection();
    initializeXRayWarning();
});
