class BloodTestSelection {
    constructor(options = {}) {
        this.selectedTests = new Set();
        this.initialTests = options.initialTests || [];
        this.allTests = [];
        this.categories = [];
        this.currentCategoryId = 'all';
        this.searchTerm = '';
        this.bloodCollectionPrice = 150;

        console.log('=== BloodTestSelection Constructor ===');
        console.log('Initial tests:', this.initialTests);
        console.log('Number of initial tests:', this.initialTests.length);

        this.init();
    }

    async init() {
        console.log('=== Initializing BloodTestSelection ===');

        // Загружаем анализы с сервера
        await this.loadBloodTests();

        // Инициализируем выбранные анализы из initialTests
        if (this.initialTests && this.initialTests.length > 0) {
            console.log('Initializing selected tests from initialTests:', this.initialTests);

            // Преобразуем строки в числа
            const initialTestIds = this.initialTests.map(id => parseInt(id));

            // Добавляем тесты в selectedTests
            initialTestIds.forEach(testId => {
                if (!isNaN(testId)) {
                    this.selectedTests.add(testId);
                }
            });

            console.log('Selected tests after initialization:', Array.from(this.selectedTests));

            // Рендерим выбранные тесты
            this.renderSelectedTests();
        } else {
            console.log('No initial tests provided');
        }

        this.bindEvents();
        this.renderCategories();
        this.renderTests();
    }

    async loadBloodTests() {
        try {
            console.log('Loading blood tests from API...');
            const response = await fetch('/timetable/api/blood-tests/');
            const data = await response.json();

            console.log('API response:', data);
            this.categories = data.categories || [];

            this.allTests = [];
            this.categories.forEach(category => {
                if (category.tests && Array.isArray(category.tests)) {
                    category.tests.forEach(test => {
                        test.category_id = category.id;
                        test.category_name = category.name;
                        // Убедимся, что id - число
                        test.id = parseInt(test.id);
                        this.allTests.push(test);
                    });
                }
            });

            console.log(`Loaded ${this.allTests.length} tests from ${this.categories.length} categories`);

        } catch (error) {
            console.error('Error loading blood tests:', error);
            const container = document.getElementById('availableBloodTests');
            if (container) {
                container.innerHTML = '<div class="alert alert-danger">Ошибка загрузки анализов</div>';
            }
        }
    }

    bindEvents() {
        const searchInput = document.getElementById('bloodTestSearch');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchTerm = e.target.value.toLowerCase();
                this.renderTests();
            });
        }

        const clearButton = document.getElementById('clearBloodTestSearch');
        if (clearButton) {
            clearButton.addEventListener('click', () => {
                if (searchInput) {
                    searchInput.value = '';
                }
                this.searchTerm = '';
                this.renderTests();
            });
        }

        // Добавляем обработчик для обновления скрытого поля при изменении выбора
        document.addEventListener('bloodTestsUpdated', () => {
            this.updateFormField();
        });
    }

    renderCategories() {
        const container = document.getElementById('bloodTestCategories');
        if (!container) return;

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
        if (!container) return;

        // Проверяем, загружены ли тесты
        if (!this.allTests || this.allTests.length === 0) {
            container.innerHTML = '<div class="text-muted text-center py-5">Загрузка анализов...</div>';
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
            container.innerHTML = '<div class="text-muted text-center py-5">Анализы не найдены</div>';
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
        if (!container) return;

        if (!this.allTests || this.allTests.length === 0) {
            container.innerHTML = '<div class="text-muted text-center py-5">Загрузка анализов...</div>';
            return;
        }

        // Получаем массив выбранных тестов
        const selectedTestsArray = Array.from(this.selectedTests)
            .map(id => this.allTests.find(test => test.id === id))
            .filter(Boolean); // Убираем undefined

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

        // Принудительно обновляем поле формы
        this.updateFormField();

        // ДЛЯ ОТЛАДКИ
        console.log('After adding test', testId, 'selected tests are:', Array.from(this.selectedTests));
    }

    removeTest(testId) {
        console.log('Removing test:', testId);
        this.selectedTests.delete(testId);
        this.renderSelectedTests();

        // Принудительно обновляем поле формы
        this.updateFormField();

        // ДЛЯ ОТЛАДКИ
        console.log('After removing test', testId, 'selected tests are:', Array.from(this.selectedTests));
    }


    updateCounters() {
        const selectedTestsArray = Array.from(this.selectedTests)
            .map(id => this.allTests.find(test => test.id === id))
            .filter(Boolean);

        const totalCount = selectedTestsArray.length;
        const testsPrice = selectedTestsArray.reduce((sum, test) => sum + (test.price || 0), 0);
        const totalPrice = testsPrice + this.bloodCollectionPrice;

        const selectedTestsCount = document.getElementById('selectedTestsCount');
        const selectedTestsPrice = document.getElementById('selectedTestsPrice');

        if (selectedTestsCount) {
            selectedTestsCount.textContent = `${totalCount} анализов`;
        }

        if (selectedTestsPrice) {
            selectedTestsPrice.textContent = `${totalPrice} руб.`;
            selectedTestsPrice.title = `Анализы: ${testsPrice} руб. + Забор крови: ${this.bloodCollectionPrice} руб.`;
        }
    }

    updateFormField() {
        const fields = document.querySelectorAll('[name="selected_blood_tests_input"]');
        console.log(`Found ${fields.length} fields with name selected_blood_tests_input`);

        // Удаляем все лишние поля
        if (fields.length > 1) {
            console.log('Removing duplicate fields...');
            for (let i = 1; i < fields.length; i++) {
                if (fields[i].parentNode) {
                    fields[i].parentNode.removeChild(fields[i]);
                }
            }
        }

        // Обновляем оставшееся поле
        const field = document.getElementById('id_selected_blood_tests');
        if (field) {
            const selectedIds = Array.from(this.selectedTests);
            field.value = selectedIds.join(',');
            console.log('Updated form field with IDs:', field.value);

            // ВАЖНОЕ ИСПРАВЛЕНИЕ: Триггерим события для формы
            field.dispatchEvent(new Event('input', { bubbles: true }));
            field.dispatchEvent(new Event('change', { bubbles: true }));

            // Также обновляем свойство value напрямую
            field.setAttribute('value', field.value);

            console.log('Field after update:', {
                id: field.id,
                name: field.name,
                value: field.value,
                attributes: {
                    value: field.getAttribute('value'),
                    'data-value': field.getAttribute('data-value')
                }
            });
        } else {
            console.error('Form field with id "id_selected_blood_tests" not found!');
        }
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    const bloodTestSection = document.getElementById('bloodTestSelectionSection');
    if (!bloodTestSection) return;

    console.log('DOM loaded, initialTestIds:', initialTestIds);
    console.log('Type of initialTestIds:', typeof initialTestIds);

    // Убедимся, что initialTestIds - массив
    let initialTests = initialTestIds;
    if (!Array.isArray(initialTestIds)) {
        console.log('initialTestIds is not array, converting...');
        if (typeof initialTestIds === 'string') {
            try {
                initialTests = JSON.parse(initialTestIds);
            } catch (e) {
                console.error('Error parsing initialTestIds:', e);
                initialTests = [];
            }
        } else {
            initialTests = [];
        }
    }

    console.log('Final initialTests for BloodTestSelection:', initialTests);

    // Инициализируем с предзагруженными анализами
    window.bloodTestSelection = new BloodTestSelection({
        initialTests: initialTests
    });

    // Обработка изменения услуги
    const serviceSelect = document.getElementById('id_service');
    if (serviceSelect) {
        const toggleBloodTestSection = () => {
            const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
            const isBloodTest = selectedOption && selectedOption.text.toLowerCase().includes('забор крови');

            console.log('Service change detected:', selectedOption ? selectedOption.text : 'none', 'Is blood test?', isBloodTest);

            if (bloodTestSection) {
                bloodTestSection.style.display = isBloodTest ? 'block' : 'none';

                if (!isBloodTest) {
                    window.bloodTestSelection.selectedTests.clear();
                    window.bloodTestSelection.renderSelectedTests();
                }
            }
        };

        serviceSelect.addEventListener('change', toggleBloodTestSection);
        // Вызываем сразу для установки начального состояния
        toggleBloodTestSection();
    }
});