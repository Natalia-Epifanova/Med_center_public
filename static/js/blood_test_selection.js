class BloodTestSelection {
    constructor(options = {}) {
        console.log('=== BloodTestSelection Constructor ===');
        console.log('Initial tests:', options.initialTests);

        // Инициализируем как Set для эффективной работы
        this.selectedTests = new Set();

        // Сохраняем initialTests для инициализации
        this.initialTests = options.initialTests || [];

        this.allTests = [];
        this.categories = [];
        this.currentCategoryId = 'all';
        this.searchTerm = '';
        this.bloodCollectionPrice = 150;
        this.servicePrice = parseFloat(options.initialServicePrice) || 0;
        this.targetDate = options.targetDate || window.selectedDate || window.originalDate || '';

        this.init();
    }

    async init() {
        console.log('=== Initializing BloodTestSelection ===');

        // Загружаем анализы с сервера
        await this.loadBloodTests();

        // Инициализируем выбранные анализы
        if (this.initialTests && this.initialTests.length > 0) {
            console.log('Setting initial tests from initialTests:', this.initialTests);
            this.initialTests.forEach(id => {
                const testId = parseInt(id);
                if (!isNaN(testId)) {
                    this.selectedTests.add(testId);
                }
            });
        }

        console.log('Selected tests after init:', Array.from(this.selectedTests));

        this.bindEvents();
        this.renderCategories();
        this.renderTests();
        this.renderSelectedTests();

        // Обновляем сумму при инициализации
        this.updateTotalSum();

        console.log('=== BloodTestSelection Initialization Complete ===');
    }

    async loadBloodTests() {
        try {
            const dateParam = this.getTargetDate();
            const url = dateParam
                ? `/appointments/api/blood-tests/?date=${encodeURIComponent(dateParam)}`
                : '/appointments/api/blood-tests/';
            console.log(`Loading blood tests from ${url}`);
            const response = await fetch(url);
            console.log('Response status:', response.status);

            const data = await response.json();
            console.log('API response data:', data);

            this.categories = data.categories || [];
            this.allTests = [];

            // Собираем все тесты из категорий
            this.categories.forEach(category => {
                console.log(`Processing category: ${category.name} with ${category.tests ? category.tests.length : 0} tests`);

                if (category.tests && Array.isArray(category.tests)) {
                    category.tests.forEach(test => {
                        test.category_id = category.id;
                        test.category_name = category.name;
                        test.id = parseInt(test.id);
                        this.allTests.push(test);
                    });
                }
            });

            console.log(`Total tests loaded: ${this.allTests.length}`);
            console.log('Categories:', this.categories);

        } catch (error) {
            console.error('Error loading blood tests:', error);
            const container = document.getElementById('availableBloodTests');
            if (container) {
                container.innerHTML = '<div class="alert alert-danger">Ошибка загрузки анализов. Пожалуйста, обновите страницу.</div>';
            }
        }
    }

    bindEvents() {
        // Поиск
        const searchInput = document.getElementById('bloodTestSearch');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchTerm = e.target.value.toLowerCase();
                this.renderTests();
            });
        }

        // Очистка поиска
        const clearButton = document.getElementById('clearBloodTestSearch');
        if (clearButton) {
            clearButton.addEventListener('click', () => {
                if (searchInput) searchInput.value = '';
                this.searchTerm = '';
                this.renderTests();
            });
        }

        // Добавляем обработчик для обновления скрытого поля при изменении выбора
        document.addEventListener('bloodTestsUpdated', () => {
            this.updateFormField();
            this.updateTotalSum();
        });

        ['id_new_appointment_date', 'id_procedural_appointment_date'].forEach(fieldId => {
            const dateInput = document.getElementById(fieldId);
            if (dateInput) {
                dateInput.addEventListener('change', async () => {
                    this.targetDate = dateInput.value;
                    await this.loadBloodTests();
                    this.renderTests();
                    this.renderSelectedTests();
                });
            }
        });
    }

    getTargetDate() {
        const dateInput = document.getElementById('id_procedural_appointment_date') ||
            document.getElementById('id_new_appointment_date');

        return (dateInput && dateInput.value) || this.targetDate || '';
    }
    // Метод для очистки всех выбранных анализов
    clearAllTests() {
        console.log('Clearing all selected blood tests');
        this.selectedTests = [];
        this.updateSelectedTestsDisplay();
        this.updateFormField();
        this.updateTotalSum();
    }
    renderCategories() {
        const container = document.getElementById('bloodTestCategories');
        if (!container) {
            console.error('Categories container not found!');
            return;
        }

        let html = `
            <button type="button" class="btn btn-outline-primary btn-sm active"
                    data-category-id="all">
                Все анализы
            </button>
        `;

        if (this.categories && this.categories.length > 0) {
            this.categories.forEach(category => {
                if (category.tests && category.tests.length > 0) {
                    html += `
                        <button type="button" class="btn btn-outline-primary btn-sm"
                                data-category-id="${category.id}">
                            ${category.name}
                        </button>
                    `;
                }
            });
        }

        container.innerHTML = html;

        container.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('#bloodTestCategories button').forEach(b => {
                    b.classList.remove('active');
                });
                e.target.classList.add('active');
                this.currentCategoryId = e.target.dataset.categoryId;
                this.renderTests();
            });
        });
    }

    renderTests() {
        const container = document.getElementById('availableBloodTests');
        if (!container) {
            console.error('Available tests container not found!');
            return;
        }

        // Проверяем, загружены ли тесты
        if (!this.allTests || this.allTests.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-5">Загрузка анализов...</div>';
            return;
        }

        let filteredTests = this.allTests.filter(test => {
            // Проверяем категорию
            const matchesCategory = this.currentCategoryId === 'all' ||
                                  test.category_id.toString() === this.currentCategoryId;

            // Проверяем поиск
            const matchesSearch = !this.searchTerm ||
                                (test.name && test.name.toLowerCase().includes(this.searchTerm)) ||
                                (test.code && test.code.toLowerCase().includes(this.searchTerm));

            // Проверяем, не выбран ли уже тест
            const notSelected = !this.selectedTests.has(test.id);

            return matchesCategory && matchesSearch && notSelected;
        });

        if (filteredTests.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-5">Анализы не найдены</div>';
            return;
        }

        container.innerHTML = filteredTests.map(test => `
            <div class="blood-test-item border-bottom py-2 px-1" data-test-id="${test.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1 me-2">
                        <div class="fw-bold small">${test.name || 'Без названия'}</div>
                        <div class="d-flex flex-wrap gap-1 mt-1">
                            <span class="badge bg-info">${test.execution_time || '1 день'}</span>
                            <span class="badge bg-success">${test.price || 0} руб.</span>
                        </div>
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-primary add-blood-test"
                            data-test-id="${test.id}" title="Добавить анализ">
                        <i class="fas fa-plus"></i>
                    </button>
                </div>
            </div>
        `).join('');

        container.querySelectorAll('.add-blood-test').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const testId = parseInt(e.target.closest('.add-blood-test').dataset.testId);
                this.addTest(testId);
            });
        });
    }

    renderSelectedTests() {
        const container = document.getElementById('selectedBloodTests');
        if (!container) {
            console.error('Selected tests container not found!');
            return;
        }

        if (!this.allTests || this.allTests.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-5">Загрузка анализов...</div>';
            return;
        }

        // Получаем массив выбранных тестов
        const selectedTestsArray = Array.from(this.selectedTests)
            .map(id => this.allTests.find(test => test.id === id))
            .filter(Boolean);

        console.log('Rendering selected tests:', selectedTestsArray);

        if (selectedTestsArray.length === 0) {
            container.innerHTML = `
                <div class="text-muted text-center py-5">
                    <i class="fas fa-inbox fa-2x mb-3"></i><br>
                    Анализы не выбраны
                </div>
            `;
        } else {
            container.innerHTML = selectedTestsArray.map(test => `
                <div class="selected-blood-test-item border-bottom py-2 px-1" data-test-id="${test.id}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1 me-2">
                            <div class="fw-bold small">${test.name || 'Без названия'}</div>
                            <div class="d-flex flex-wrap gap-1 mt-1">
                                <span class="badge bg-info">${test.execution_time || '1 день'}</span>
                                <span class="badge bg-success">${test.price || 0} руб.</span>
                            </div>
                        </div>
                        <button type="button" class="btn btn-sm btn-outline-danger remove-blood-test"
                                data-test-id="${test.id}" title="Удалить анализ">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
            `).join('');
        }

        this.updateCounters();
        this.updateFormField();
        this.updateTotalSum(); // Обновляем сумму

        // Обновляем список доступных тестов
        this.renderTests();

        // Добавляем обработчики для кнопок удаления
        container.querySelectorAll('.remove-blood-test').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const testId = parseInt(e.target.closest('.remove-blood-test').dataset.testId);
                this.removeTest(testId);
            });
        });
    }

    addTest(testId) {
        console.log('Adding test:', testId);
        this.selectedTests.add(testId);
        this.renderSelectedTests();
    }

    removeTest(testId) {
        console.log('Removing test:', testId);
        this.selectedTests.delete(testId);
        this.renderSelectedTests();
    }

    clearSelectedTests() {
        console.log('Clearing all selected tests');
        this.selectedTests.clear();
        this.renderSelectedTests();
        this.updateTotalSum(0); // Обнуляем сумму
    }

    updateCounters() {
        const selectedTestsArray = Array.from(this.selectedTests)
            .map(id => this.allTests.find(test => test.id === id))
            .filter(Boolean);

        const totalCount = selectedTestsArray.length;
        const testsPrice = selectedTestsArray.reduce((sum, test) => sum + (test.price || 0), 0);
        const servicePrice = this.getCurrentServicePrice();
        const totalPrice = testsPrice + servicePrice;

        const selectedTestsCount = document.getElementById('selectedTestsCount');
        const selectedTestsPrice = document.getElementById('selectedTestsPrice');

        if (selectedTestsCount) {
            selectedTestsCount.textContent = `${totalCount} анализов`;
        }

        if (selectedTestsPrice) {
            selectedTestsPrice.textContent = `${totalPrice} руб.`;
            selectedTestsPrice.title = `Анализы: ${testsPrice} руб. + Забор крови: ${servicePrice} руб.`;
        }
    }

    setServicePrice(price) {
        const parsedPrice = parseFloat(price);
        if (!Number.isNaN(parsedPrice)) {
            this.servicePrice = parsedPrice;
        }
    }

    getCurrentServicePrice() {
        const serviceSelect = document.getElementById('id_service');
        if (!serviceSelect || !serviceSelect.value) {
            return this.servicePrice || 0;
        }

        const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
        if (!selectedOption) {
            return this.servicePrice || 0;
        }

        const datasetPrice = parseFloat(selectedOption.dataset.price);
        if (!Number.isNaN(datasetPrice)) {
            this.servicePrice = datasetPrice;
            return datasetPrice;
        }

        if (this.servicePrice > 0) {
            selectedOption.dataset.price = this.servicePrice;
            return this.servicePrice;
        }

        const priceMatch = selectedOption.textContent.match(/[\d\s]+(?:[.,]\d+)?\s*руб\.?/);
        if (priceMatch) {
            const normalizedPrice = priceMatch[0].replace(/\s/g, '').replace(',', '.');
            const parsedPrice = parseFloat(normalizedPrice.replace(/[^\d.]/g, ''));
            if (!Number.isNaN(parsedPrice)) {
                this.servicePrice = parsedPrice;
                selectedOption.dataset.price = parsedPrice;
                return parsedPrice;
            }
        }

        return this.bloodCollectionPrice;
    }


    // НОВАЯ ФУНКЦИЯ: Обновление итоговой суммы
    updateTotalSum() {
        console.log('=== updateTotalSum called ===');

        // Считаем сумму анализов
        const testsPrice = this.getTotalPrice();

        const servicePrice = this.getCurrentServicePrice();

        // Общая сумма
        const totalSum = servicePrice + testsPrice;

        console.log('Calculating total sum:', {
            servicePrice,
            testsPrice,
            totalSum
        });

        // Обновляем отображение
        const totalElement = document.getElementById('selectedTestsPrice');
        if (totalElement) {
            totalElement.textContent = totalSum + ' руб.';
        }

        // Обновляем скрытое поле
        const totalField = document.getElementById('id_total_sum');
        if (totalField) {
            totalField.value = totalSum;
            // ВАЖНОЕ ИСПРАВЛЕНИЕ: устанавливаем атрибут value для DOM
            totalField.setAttribute('value', totalSum);
            console.log('Updated total_sum field value:', totalSum);
        }

        return totalSum;
    }

    // Добавьте метод getTotalPrice для подсчета суммы анализов
    getTotalPrice() {
        const selectedTestsArray = Array.from(this.selectedTests)
            .map(id => this.allTests.find(test => test.id === id))
            .filter(Boolean);

        return selectedTestsArray.reduce((sum, test) => sum + (parseFloat(test.price) || 0), 0);
    }

    // Добавьте функцию для правильного обновления формы
    updateFormField() {
        const selectedIds = Array.from(this.selectedTests.values());
        const field = document.getElementById('id_selected_blood_tests');

        if (field) {
            field.value = selectedIds.join(',');
            console.log('Updated selected_blood_tests_input:', field.value);

            // Небольшая задержка для гарантии обновления
            setTimeout(() => {
                this.updateTotalSum();
            }, 50); // 50ms задержка
        }
    }
}


// Экспорт класса для использования
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BloodTestSelection;
}

// Глобальная функция для очистки выбранных анализов (если нужно вызывать извне)
function clearBloodTestsSelection() {
    if (window.bloodTestSelection && typeof window.bloodTestSelection.clearSelectedTests === 'function') {
        window.bloodTestSelection.clearSelectedTests();
    }
}

// Функция для обновления суммы при изменении услуги
function handleServiceChangeForBloodTests() {
    if (window.bloodTestSelection && typeof window.bloodTestSelection.updateTotalSum === 'function') {
        window.bloodTestSelection.updateTotalSum();
    }
}


// Обработчик события перед отправкой формы
document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form[method="post"]');
    if (form) {
        form.addEventListener('submit', function(e) {
            // Принудительно обновляем total_sum перед отправкой БЕЗ отмены отправки
            if (window.bloodTestSelection && typeof window.bloodTestSelection.updateTotalSum === 'function') {
                window.bloodTestSelection.updateTotalSum();
            }

            // Мгновенно обновляем значение в DOM
            const totalField = document.getElementById('id_total_sum');
            if (totalField) {
                // Принудительно обновляем атрибут value
                totalField.setAttribute('value', totalField.value);
            }

            console.log('Form submitted with total_sum:', document.getElementById('id_total_sum').value);
        });
    }
});
