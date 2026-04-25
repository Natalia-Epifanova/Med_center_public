function initializeBloodTestSelection() {
    const serviceSelect = document.getElementById('id_service');
    const bloodTestSection = document.getElementById('bloodTestSelectionSection');

    if (!serviceSelect || !bloodTestSection) return;

    // Проверяем, есть ли уже экземпляр bloodTestSelection
    if (!window.bloodTestSelection) {
        // Загружаем класс BloodTestSelection если он не загружен
        if (typeof BloodTestSelection !== 'undefined') {
            window.bloodTestSelection = new BloodTestSelection({
                initialTests: []
            });
        } else {
            // Если класс не загружен, пытаемся загрузить скрипт
            const script = document.createElement('script');
            script.src = '/static/js/blood_test_selection.js?v=' + new Date().getTime();
            script.onload = function() {
                if (typeof BloodTestSelection !== 'undefined') {
                    window.bloodTestSelection = new BloodTestSelection({
                        initialTests: []
                    });
                }
            };
            document.head.appendChild(script);
        }
    }

    // Функция для показа/скрытия блока анализов
    function toggleBloodTestSection() {
        const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
        const serviceName = selectedOption ? selectedOption.text.toLowerCase() : '';

        // Показываем блок только для услуги "Забор крови"
        const isBloodTest = serviceName.includes('забор крови') ||
                           serviceName.includes('анализ') ||
                           serviceName.includes('blood');

        bloodTestSection.style.display = isBloodTest ? 'block' : 'none';

        // Если выбрана услуга забора крови, обновляем сумму
        if (isBloodTest && window.bloodTestSelection) {
            window.bloodTestSelection.updateTotalSum();
        }

        // Очищаем выбор если переключились на другую услугу
        if (!isBloodTest && window.bloodTestSelection) {
            window.bloodTestSelection.clearSelectedTests();
        }
    }

    // Обработчик изменения услуги
    serviceSelect.addEventListener('change', toggleBloodTestSection);

    // Инициализация при загрузке
    toggleBloodTestSection();
}
// Добавьте эту функцию после initializeBloodTestSelection()
