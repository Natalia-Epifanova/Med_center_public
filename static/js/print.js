/**
 * Функции для печати расписания
 */

function printSchedule() {
    console.log('=== PRINT DEBUG ===');

    // Получаем дату из переменной, установленной в шаблоне
    const scheduleDate = window.selectedDate;

    if (!scheduleDate) {
        console.error('ERROR: selectedDate is not defined!');
        console.log('Available global variables:', Object.keys(window).filter(key => key.includes('Date')));

        // Попробуем найти дату на странице другими способами
        const dateFromPage = findDateOnPage();
        if (dateFromPage) {
            console.log('Found date on page:', dateFromPage);
            window.selectedDate = dateFromPage;
        } else {
            console.log('Using current date as fallback');
            window.selectedDate = new Date().toLocaleDateString('ru-RU');
        }
    }

    console.log('Printing schedule for date:', window.selectedDate);

    // Создаем клон основного контента для печати
    const originalContainer = document.querySelector('.timetable-container-fluid');
    if (!originalContainer) {
        console.error('Main container not found');
        window.print();
        return;
    }

    const printContainer = originalContainer.cloneNode(true);

    // Убираем скролл контейнер
    const scrollContainer = printContainer.querySelector('.timetable-cards-scroll-container');
    if (scrollContainer) {
        scrollContainer.style.cssText = 'overflow: visible; padding-bottom: 0; margin: 0;';
    }

    // Устанавливаем грид для карточек - 4 в ряд
    const cardsGrid = printContainer.querySelector('.timetable-cards-grid');
    if (cardsGrid) {
        cardsGrid.style.cssText = 'display: grid !important; grid-template-columns: repeat(4, 1fr) !important; gap: 3mm !important; width: 100% !important;';
    }

    // Скрываем колонку "Действия"
    const actionHeaders = printContainer.querySelectorAll('.timetable-table-sm th:nth-child(5)');
    const actionCells = printContainer.querySelectorAll('.timetable-table-sm td:nth-child(5)');
    actionHeaders.forEach(el => el.style.display = 'none');
    actionCells.forEach(el => el.style.display = 'none');

    // Убираем ссылки из времени слотов и заменяем на обычный текст
    const timeCells = printContainer.querySelectorAll('.timetable-table-sm td:nth-child(1)');
    timeCells.forEach(cell => {
        const link = cell.querySelector('a');
        if (link) {
            // Сохраняем текст времени
            const timeText = link.textContent || link.innerText;
            // Удаляем ссылку и оставляем только текст
            const strongElement = link.querySelector('strong');
            if (strongElement) {
                link.parentNode.replaceChild(strongElement, link);
            } else {
                // Если нет strong, создаем новый элемент с текстом
                const timeSpan = document.createElement('span');
                timeSpan.innerHTML = `<strong>${timeText}</strong>`;
                link.parentNode.replaceChild(timeSpan, link);
            }
        }

        // Также обрабатываем дополнительные элементы времени (перерывы, бейджи)
        const additionalElements = cell.querySelectorAll('br, small, .badge');
        additionalElements.forEach(el => {
            // Просто оставляем их как есть, но убираем возможные ссылки
            const nestedLinks = el.querySelectorAll('a');
            nestedLinks.forEach(nestedLink => {
                const nestedText = nestedLink.textContent || nestedLink.innerText;
                nestedLink.parentNode.replaceChild(document.createTextNode(nestedText), nestedLink);
            });
        });
    });

    // Создаем окно для печати
    const printWindow = window.open('', '_blank', 'width=1000,height=700');
    if (!printWindow) {
        console.error('Could not open print window');
        window.print();
        return;
    }

    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Расписание на ${window.selectedDate}</title>
            <style>
                body {
                    margin: 0;
                    padding: 8mm;
                    font-family: Arial, sans-serif;
                    font-size: 10px;
                }
                .timetable-cards-grid {
                    display: grid;
                    grid-template-columns: repeat(4, 1fr);
                    gap: 3mm;
                    width: 100%;
                }
                .card {
                    border: 1px solid #000;
                    page-break-inside: avoid;
                    break-inside: avoid;
                    min-height: 80mm;
                }
                .table {
                    font-size: 6px;
                    width: 100%;
                }
                th:nth-child(5), td:nth-child(5) {
                    display: none !important;
                }
                /* Убираем все ссылки в таблице */
                .table a {
                    color: black !important;
                    text-decoration: none !important;
                }
                .table td:nth-child(1) a {
                    display: none !important;
                }
                @page {
                    size: A4 landscape;
                    margin: 8mm;
                }
                @media print {
                    body { margin: 0; padding: 0; }
                    .timetable-cards-grid { gap: 2mm; }
                }
            </style>
        </head>
        <body>
            <h2 style="text-align: center; margin-bottom: 5mm; font-size: 14px;">Расписание на ${window.selectedDate}</h2>
            ${printContainer.outerHTML}
        </body>
        </html>
    `);

    printWindow.document.close();

    // Даем время на загрузку и затем печатаем
    setTimeout(() => {
        printWindow.print();
        setTimeout(() => printWindow.close(), 500);
    }, 500);
}

/**
 * Функция для поиска даты на странице
 */
function findDateOnPage() {
    // Способ 1: Из заголовка с классом .timetable-current-date
    const dateHeader = document.querySelector('.timetable-current-date strong');
    if (dateHeader) {
        const text = dateHeader.textContent.trim();
        console.log('Found date in header:', text);
        return text;
    }

    // Способ 2: Из заголовка навигации
    const leadText = document.querySelector('.lead');
    if (leadText) {
        const text = leadText.textContent.trim();
        const dateMatch = text.match(/(\d{2}\.\d{2}\.\d{4})/);
        if (dateMatch) {
            console.log('Found date in lead text:', dateMatch[1]);
            return dateMatch[1];
        }
    }

    // Способ 3: Из кнопки печати
    const printButton = document.querySelector('button[onclick*="printSchedule"]');
    if (printButton) {
        const buttonText = printButton.textContent || printButton.innerText;
        const dateMatch = buttonText.match(/(\d{2}\.\d{2}\.\d{4})/);
        if (dateMatch) {
            console.log('Found date on print button:', dateMatch[1]);
            return dateMatch[1];
        }
    }

    // Способ 4: Из скрытого поля с датой
    const hiddenDate = document.querySelector('input[name="date"]');
    if (hiddenDate && hiddenDate.value) {
        const dateValue = hiddenDate.value;
        // Преобразуем из формата YYYY-MM-DD в DD.MM.YYYY
        const parts = dateValue.split('-');
        if (parts.length === 3) {
            const formattedDate = `${parts[2]}.${parts[1]}.${parts[0]}`;
            console.log('Found date in hidden field:', formattedDate);
            return formattedDate;
        }
    }

    return null;
}

/**
 * Инициализация обработчиков для печати
 */
function initializePrintHandlers() {
    console.log('Initializing print handlers...');
    console.log('window.selectedDate on init:', window.selectedDate);

    // Обработка нажатия Ctrl+P
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
            e.preventDefault();
            printSchedule();
        }
    });

    // Делаем функцию глобально доступной для onclick
    window.printSchedule = printSchedule;
}

// Инициализируем при загрузке документа
document.addEventListener('DOMContentLoaded', initializePrintHandlers);