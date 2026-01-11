// static/js/patient_live_search.js

document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('live-search');
    const searchResults = document.getElementById('search-results');
    const resultsContainer = document.getElementById('results-container');
    const resultsCount = document.getElementById('results-count');
    const clearBtn = document.getElementById('clear-search');
    const resetBtn = document.getElementById('reset-search');
    const patientsTable = document.getElementById('patients-table-section');
    const paginationSection = document.getElementById('pagination-section');

    let searchTimeout;
    let currentSearch = '';

    // Инициализация поиска
    function initializeLiveSearch() {
        if (!searchInput) return;

        // Обработчик ввода
        searchInput.addEventListener('input', handleSearchInput);

        // Кнопка очистки
        if (clearBtn) {
            clearBtn.addEventListener('click', clearSearch);
        }

        // Кнопка сброса
        if (resetBtn) {
            resetBtn.addEventListener('click', resetSearch);
        }

        // Загрузка с сохраненными параметрами поиска
        const urlParams = new URLSearchParams(window.location.search);
        const savedSearch = urlParams.get('search');
        if (savedSearch) {
            searchInput.value = savedSearch;
            if (savedSearch.length >= 3) {
                performSearch(savedSearch);
            }
        }
    }

    // Обработчик ввода
    function handleSearchInput(e) {
        const query = e.target.value.trim();

        // Очищаем предыдущий таймер
        clearTimeout(searchTimeout);

        if (query.length < 3) {
            if (query.length === 0) {
                hideResults();
                restoreTable();
            }
            return;
        }

        // Обновляем URL без перезагрузки
        updateUrl(query);

        // Запускаем поиск с задержкой
        searchTimeout = setTimeout(() => {
            performSearch(query);
        }, 300);
    }

    // Выполнение поиска
    function performSearch(query) {
        if (query === currentSearch) return;

        currentSearch = query;

        // Показываем индикатор загрузки
        showLoading();

        // Выполняем поиск
        fetch(`/patients/api/search-patients/?q=${encodeURIComponent(query)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Ошибка поиска');
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    showError(data.error);
                    return;
                }

                displayResults(data.patients || [], query);
            })
            .catch(error => {
                showError(`Ошибка при поиске: ${error.message}`);
            })
            .finally(() => {
                // Скрываем индикатор загрузки
                hideLoading();
            });
    }

    // Отображение результатов
    function displayResults(patients, query) {
        // Скрываем таблицу и пагинацию
        if (patientsTable) patientsTable.style.display = 'none';
        if (paginationSection) paginationSection.style.display = 'none';

        // Очищаем контейнер
        resultsContainer.innerHTML = '';

        if (!patients || patients.length === 0) {
            resultsContainer.innerHTML = `
                <div class="list-group-item text-center text-muted py-4">
                    <i class="fas fa-users fa-2x mb-3"></i>
                    <p class="mb-1">Пациенты не найдены</p>
                    <small class="text-muted">Попробуйте изменить поисковый запрос</small>
                </div>
            `;
            resultsCount.textContent = '0';
            searchResults.style.display = 'block';
            return;
        }

        // Обновляем счетчик
        resultsCount.textContent = patients.length;

        // Добавляем каждого пациента
        patients.forEach(patient => {
            const resultItem = createResultItem(patient, query);
            resultsContainer.appendChild(resultItem);
        });

        // Показываем результаты
        searchResults.style.display = 'block';
    }

    // Создание элемента результата
    function createResultItem(patient, query) {
        const item = document.createElement('div');
        item.className = 'list-group-item patient-search-result';

        // Подсветка совпадений
        const highlightedName = highlightText(patient.full_name, query);
        const highlightedPhone = patient.phone_number ? highlightText(patient.phone_number, query) : '-';
        const highlightedCard = patient.card_number ? highlightText(patient.card_number, query) : '-';
        const highlightedDate = patient.date_of_birth ? highlightText(patient.date_of_birth, query) : '-';

        item.innerHTML = `
            <div class="row align-items-center">
                <div class="col-md-3">
                    <strong class="d-block">${highlightedName}</strong>
                    <small class="text-muted">${patient.date_of_birth || 'Дата рождения не указана'}</small>
                </div>
                <div class="col-md-2">
                    <div class="text-truncate">${highlightedPhone}</div>
                    <small class="text-muted">Телефон</small>
                </div>
                <div class="col-md-2">
                    <div class="text-truncate">${highlightedCard}</div>
                    <small class="text-muted">Карта (платно)</small>
                </div>
                <div class="col-md-2">
                    <div class="text-truncate">${patient.card_number_IP || '-'}</div>
                    <small class="text-muted">Карта (ИП)</small>
                </div>
                <div class="col-md-2">
                    <div class="text-truncate">${patient.card_number_OMS || '-'}</div>
                    <small class="text-muted">Карта (ОМС)</small>
                </div>
                <div class="col-md-1">
                    <div class="d-flex gap-1 justify-content-end">
                        <a href="/patients/${patient.id}/"
                           class="btn btn-sm btn-outline-info"
                           title="Подробнее">
                            <i class="fas fa-eye"></i>
                        </a>
                        <a href="/patients/${patient.id}/edit/"
                           class="btn btn-sm btn-outline-warning"
                           title="Редактировать">
                            <i class="fas fa-edit"></i>
                        </a>
                    </div>
                </div>
            </div>
        `;

        return item;
    }

    // Подсветка текста
    function highlightText(text, query) {
        if (!text || !query) return text;

        const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${escapedQuery})`, 'gi');

        return text.toString().replace(regex, '<span class="search-highlight">$1</span>');
    }

    // Показать индикатор загрузки
    function showLoading() {
        resultsContainer.innerHTML = `
            <div class="list-group-item text-center py-4">
                <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
                <span class="text-muted">Поиск пациентов...</span>
            </div>
        `;
        searchResults.style.display = 'block';
        resultsCount.textContent = '...';
    }

    // Скрыть индикатор загрузки
    function hideLoading() {
        // Уже обрабатывается в displayResults
    }

    // Показать ошибку
    function showError(message) {
        resultsContainer.innerHTML = `
            <div class="list-group-item text-center text-danger py-4">
                <i class="fas fa-exclamation-triangle fa-2x mb-3"></i>
                <p class="mb-0">${message}</p>
            </div>
        `;
        resultsCount.textContent = '0';
        searchResults.style.display = 'block';
    }

    // Скрыть результаты
    function hideResults() {
        searchResults.style.display = 'none';
        currentSearch = '';
    }

    // Восстановить таблицу
    function restoreTable() {
        if (patientsTable) patientsTable.style.display = 'block';
        if (paginationSection) paginationSection.style.display = 'block';
        hideResults();
    }

    // Очистить поиск
    function clearSearch() {
        searchInput.value = '';
        searchInput.focus();
        restoreTable();
        updateUrl('');
    }

    // Сбросить поиск
    function resetSearch() {
        searchInput.value = '';
        restoreTable();
        updateUrl('');
        window.location.href = window.location.pathname; // Полный сброс URL
    }

    // Обновить URL без перезагрузки страницы
    function updateUrl(query) {
        const url = new URL(window.location);

        if (query) {
            url.searchParams.set('search', query);
            url.searchParams.delete('page'); // Сбрасываем пагинацию при поиске
        } else {
            url.searchParams.delete('search');
        }

        window.history.replaceState({}, '', url);
    }

    // Запуск
    initializeLiveSearch();
});