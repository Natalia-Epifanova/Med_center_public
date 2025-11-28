class BloodTestSelection {
    constructor() {
        this.categories = [];
        this.allTests = [];
        this.selectedTests = new Set();
        this.currentCategoryId = 'all';
        this.searchTerm = '';
        this.bloodCollectionPrice = 150;

        this.init();
    }

    async init() {
        await this.loadBloodTests();
        this.bindEvents();
        this.renderCategories();
        this.renderTests();
        this.updateFormField(); // Инициализируем поле формы
    }

    async loadBloodTests() {
        try {
            const response = await fetch('/timetable/api/blood-tests/');
            const data = await response.json();
            this.categories = data.categories;

            this.allTests = [];
            this.categories.forEach(category => {
                category.tests.forEach(test => {
                    test.category_id = category.id;
                    test.category_name = category.name;
                    this.allTests.push(test);
                });
            });

        } catch (error) {
            console.error('Error loading blood tests:', error);
            document.getElementById('availableBloodTests').innerHTML =
                '<div class="alert alert-danger">Ошибка загрузки анализов</div>';
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

        this.categories.forEach(category => {
            html += `
                <button type="button" class="btn btn-outline-primary btn-sm"
                        data-category-id="${category.id}">
                    ${category.name}
                </button>
            `;
        });

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

        let filteredTests = this.allTests.filter(test => {
            const matchesCategory = this.currentCategoryId === 'all' ||
                                  test.category_id.toString() === this.currentCategoryId;
            const matchesSearch = !this.searchTerm ||
                                test.name.toLowerCase().includes(this.searchTerm) ||
                                (test.code && test.code.toLowerCase().includes(this.searchTerm));
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
                        <div class="fw-bold small">${test.name}</div>
                        <div class="d-flex flex-wrap gap-1 mt-1">
                            <span class="badge bg-info">${test.execution_time}</span>
                            <span class="badge bg-success">${test.price} руб.</span>
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

        const selectedTestsArray = Array.from(this.selectedTests).map(id =>
            this.allTests.find(test => test.id === id)
        ).filter(Boolean);

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
                            <div class="fw-bold small">${test.name}</div>
                            <div class="d-flex flex-wrap gap-1 mt-1">
                                <span class="badge bg-info">${test.execution_time}</span>
                                <span class="badge bg-success">${test.price} руб.</span>
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
        this.renderTests();

        container.querySelectorAll('.remove-blood-test').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const testId = parseInt(e.target.closest('.remove-blood-test').dataset.testId);
                this.removeTest(testId);
            });
        });
    }

    addTest(testId) {
        this.selectedTests.add(testId);
        this.renderSelectedTests();
    }

    removeTest(testId) {
        this.selectedTests.delete(testId);
        this.renderSelectedTests();
    }

    updateCounters() {
        const selectedTestsArray = Array.from(this.selectedTests).map(id =>
            this.allTests.find(test => test.id === id)
        ).filter(Boolean);

        const totalCount = selectedTestsArray.length;
        const testsPrice = selectedTestsArray.reduce((sum, test) => sum + test.price, 0);
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
        const field = document.getElementById('id_selected_blood_tests');
        if (field) {
            const selectedIds = Array.from(this.selectedTests);
            field.value = selectedIds.join(',');
            console.log('Updated form field with IDs:', field.value);

            // ДОБАВЬТЕ ЭТУ ПРОВЕРКУ ДЛЯ ОТЛАДКИ
            console.log('Form field element:', field);
            console.log('Form field name:', field.name);
            console.log('Form field value:', field.value);
        } else {
            console.error('Form field with id "id_selected_blood_tests" not found!');
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const bloodTestSection = document.getElementById('bloodTestSelectionSection');
    if (!bloodTestSection) return;

    window.bloodTestSelection = new BloodTestSelection();

    const serviceSelect = document.getElementById('id_service');
    if (serviceSelect) {
        const toggleBloodTestSection = () => {
            const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
            const isBloodTest = selectedOption && selectedOption.text.toLowerCase().includes('забор крови');

            if (bloodTestSection) {
                bloodTestSection.style.display = isBloodTest ? 'block' : 'none';

                // Если выбрана не услуга забора крови, очищаем выбранные анализы
                if (!isBloodTest) {
                    window.bloodTestSelection.selectedTests.clear();
                    window.bloodTestSelection.renderSelectedTests();
                }
            }
        };

        serviceSelect.addEventListener('change', toggleBloodTestSection);
        toggleBloodTestSection();
    }
});