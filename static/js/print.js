/**
 * Функции для печати расписания
 */

function printSchedule() {
    console.log('=== PRINT DEBUG ===');

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
            <title>Расписание на {{ selected_date|date:"d.m.Y" }}</title>
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
            <h2 style="text-align: center; margin-bottom: 5mm; font-size: 14px;">Расписание на {{ selected_date|date:"d.m.Y" }}</h2>
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
 * Инициализация обработчиков для печати
 */
function initializePrintHandlers() {
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