/**
 * Функции для печати расписания
 */

function printSchedule() {
    console.log('=== PRINT SCHEDULE ===');

    // Получаем дату
    const scheduleDate = window.selectedDate || findDateOnPage() || new Date().toLocaleDateString('ru-RU');
    console.log('Printing schedule for date:', scheduleDate);

    // Получаем все кабинеты
    const cabinetCards = document.querySelectorAll('.timetable-cabinet-column');
    if (!cabinetCards.length) {
        console.error('No cabinet cards found');
        window.print();
        return;
    }

    console.log(`Found ${cabinetCards.length} cabinet cards`);

    // Создаем копии карточек для печати
    const printCards = [];
    cabinetCards.forEach((card, index) => {
        const clonedCard = card.cloneNode(true);

        // 1. Упрощаем заголовок карточки
        const cardHeader = clonedCard.querySelector('.card-header');
        if (cardHeader) {
            // Убираем иконку двери
            const doorIcon = cardHeader.querySelector('.fa-door-open');
            if (doorIcon) doorIcon.remove();

            // Убираем все дополнительные тексты кроме "Кабинет X"
            const cardTitle = cardHeader.querySelector('.card-title');
            if (cardTitle) {
                const text = cardTitle.textContent.trim();
                // Оставляем только номер кабинета
                const cabinetMatch = text.match(/Кабинет\s+\d+/);
                if (cabinetMatch) {
                    cardTitle.innerHTML = `<strong>${cabinetMatch[0]}</strong>`;
                }
            }
        }

        // 2. Упрощаем заголовок врача в теле карточки
        const doctorHeaders = clonedCard.querySelectorAll('.doctor-header');
        doctorHeaders.forEach(header => {
            // Находим ФИО врача в заголовке
            const doctorElements = header.querySelectorAll('*');
            let doctorName = '';

            doctorElements.forEach(el => {
                const text = el.textContent.trim();
                // Ищем ФИО врача в формате "Фамилия И.О."
                const doctorMatch = text.match(/[А-Я][а-я]+\s+[А-Я]\.\s*[А-Я]\./);
                if (doctorMatch && !doctorName) {
                    doctorName = doctorMatch[0];
                }
            });

            // Очищаем весь header и добавляем только ФИО врача
            if (doctorName) {
                header.innerHTML = `<strong>${doctorName}</strong>`;
                header.style.cssText = 'padding: 2px; margin-bottom: 2px; font-size: 9pt; text-align: center; background-color: #ffffcc;';
            }

            // Убираем кнопку "Удалить все слоты"
            const deleteButton = header.querySelector('.delete-all-slots-btn');
            if (deleteButton) deleteButton.remove();

            // Убираем специализацию врача
            const specialization = header.querySelector('strong.text-dark');
            if (specialization) specialization.remove();

            // Убираем комментарий врача
            const comment = header.querySelector('strong.text-danger');
            if (comment) comment.remove();

            // Убираем все дополнительные тексты (название кабинета, стоимость и т.д.)
            const allStrongElements = header.querySelectorAll('strong');
            allStrongElements.forEach((el, idx) => {
                if (idx > 0) { // Оставляем только первый элемент (ФИО)
                    el.remove();
                }
            });
        });

        // 3. Убираем кнопки действий и связанные элементы
        const actionCells = clonedCard.querySelectorAll('.timetable-table-sm td:nth-child(5)');
        actionCells.forEach(cell => cell.style.display = 'none');

        const actionHeaders = clonedCard.querySelectorAll('.timetable-table-sm th:nth-child(5)');
        actionHeaders.forEach(header => header.style.display = 'none');

        // 4. Преобразуем ссылки в обычный текст
        const timeLinks = clonedCard.querySelectorAll('.timetable-table-sm td:nth-child(1) a');
        timeLinks.forEach(link => {
            const timeText = link.textContent || link.innerText;
            const timeSpan = document.createElement('span');
            timeSpan.innerHTML = `<strong>${timeText}</strong>`;
            link.parentNode.replaceChild(timeSpan, link);
        });

        const patientLinks = clonedCard.querySelectorAll('.patient-link');
        patientLinks.forEach(link => {
            const patientText = link.textContent || link.innerText;
            const patientSpan = document.createElement('span');
            patientSpan.innerHTML = `<strong>${patientText}</strong>`;
            link.parentNode.replaceChild(patientSpan, link);
        });

        // Убираем все остальные ссылки
        const otherLinks = clonedCard.querySelectorAll('a');
        otherLinks.forEach(link => {
            if (!link.closest('.timetable-table-sm td:nth-child(1)')) {
                const text = link.textContent || link.innerText;
                link.parentNode.replaceChild(document.createTextNode(text), link);
            }
        });

        // 5. Убираем пустые строки (элементы с "-" или пустые)
        const textMutedElements = clonedCard.querySelectorAll('small.text-muted');
        textMutedElements.forEach(el => {
            const text = el.textContent.trim();
            if (text === '-' || text === '' || text === 'Недоступно для записи') {
                el.style.display = 'none';
            }
        });

        printCards.push(clonedCard.outerHTML);
    });

    // Разбиваем на группы по 3 карточки
    const groupedCards = [];
    for (let i = 0; i < printCards.length; i += 3) {
        groupedCards.push(printCards.slice(i, i + 3));
    }

    console.log(`Created ${groupedCards.length} pages with 3 cabinets each`);

    // Создаем HTML для печати БЕЗ ЗАГОЛОВКОВ
    let printHTML = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Расписание на ${scheduleDate}</title>
            <meta charset="UTF-8">
            <style>
                /* Общие стили печати */
                body {
                    margin: 0;
                    padding: 3mm;
                    font-family: Arial, sans-serif;
                    font-size: 8pt;
                    background: white;
                    color: black;
                }

                .print-page {
                    page-break-after: always;
                    break-after: page;
                }

                /* Сетка карточек - 3 в ряд */
                .print-cards-grid {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 2mm;
                    width: 100%;
                    min-height: 170mm;
                }

                /* Стили карточки кабинета */
                .print-cabinet-card {
                    border: 1px solid #000;
                    border-radius: 1mm;
                    overflow: hidden;
                    page-break-inside: avoid;
                    break-inside: avoid;
                    height: 165mm;
                    display: flex;
                    flex-direction: column;
                }

                .print-cabinet-header {
                    background-color: #f0f0f0 !important;
                    color: black !important;
                    padding: 1mm 2mm !important;
                    text-align: center;
                    font-size: 9pt;
                    font-weight: bold;
                    border-bottom: 1px solid #000;
                }

                .print-cabinet-body {
                    padding: 1mm;
                    flex-grow: 1;
                    overflow: hidden;
                }

                /* Таблица в карточке */
                .print-table {
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 6pt;
                    table-layout: fixed;
                }

                .print-table th {
                    background-color: #f8f8f8;
                    border: 0.5px solid #ccc;
                    padding: 0.5mm 1mm;
                    text-align: left;
                    font-weight: bold;
                    height: 8mm;
                }

                .print-table td {
                    border: 0.5px solid #ccc;
                    padding: 0.5mm 1mm;
                    vertical-align: top;
                    height: 6mm;
                }

                .print-table tr:nth-child(even) {
                    background-color: #fafafa;
                }

                /* Ширины колонок */
                .print-table th:nth-child(1),
                .print-table td:nth-child(1) {
                    width: 20%;
                }

                .print-table th:nth-child(2),
                .print-table td:nth-child(2) {
                    width: 25%;
                }

                .print-table th:nth-child(3),
                .print-table td:nth-child(3) {
                    width: 35%;
                }

                .print-table th:nth-child(4),
                .print-table td:nth-child(4) {
                    width: 20%;
                }

                /* Скрываем колонку действий */
                .print-table th:nth-child(5),
                .print-table td:nth-child(5) {
                    display: none;
                }

                /* Стили для разных типов слотов */
                .timetable-slot-dms {
                    background-color: #ffeef8 !important;
                }

                .timetable-slot-oms {
                    background-color: #f0e8ff !important;
                }

                .timetable-slot-break {
                    background-color: #fff3cd !important;
                }

                .timetable-slot-working {
                    background-color: #ffffff !important;
                }

                /* Бейджи типов оплаты */
                .badge {
                    display: inline-block;
                    padding: 0.2mm 0.5mm;
                    font-size: 5pt;
                    font-weight: bold;
                    border-radius: 0.5mm;
                    margin-top: 0.2mm;
                    border: 0.3px solid #ccc;
                }

                .bg-pink {
                    background-color: #ffcce0 !important;
                    color: #333 !important;
                }

                .bg-purple {
                    background-color: #e6d9ff !important;
                    color: #333 !important;
                }

                .bg-success {
                    background-color: #d4edda !important;
                    color: #333 !important;
                }

                .bg-secondary {
                    background-color: #e2e3e5 !important;
                    color: #333 !important;
                }

                /* Заголовок врача */
                .doctor-header {
                    background-color: #ffffcc !important;
                    border: 0.5px solid #ffcc00;
                    border-radius: 1mm;
                    padding: 1mm;
                    margin: 1mm 0;
                    text-align: center;
                    font-size: 7pt;
                    font-weight: bold;
                }

                /* Убираем все ссылки */
                a {
                    color: black !important;
                    text-decoration: none !important;
                }

                /* Настройки страницы */
                @page {
                    size: A4 landscape;
                    margin: 3mm;
                }

                @media print {
                    body {
                        padding: 0;
                        margin: 0;
                    }

                    .print-page {
                        margin: 0;
                    }

                    .print-cards-grid {
                        gap: 2mm;
                        min-height: 170mm;
                    }

                    .print-cabinet-card {
                        height: 165mm;
                    }
                }

                /* Номер страницы */
                .page-number {
                    position: absolute;
                    bottom: 1mm;
                    right: 3mm;
                    font-size: 7pt;
                    color: #666;
                }

                /* Скрываем легенду */
                .print-legend {
                    display: none !important;
                }

                /* Скрываем элементы управления */
                .no-print {
                    display: none !important;
                }
            </style>
        </head>
        <body>
    `;

    // Добавляем каждую страницу БЕЗ ШАПКИ
    groupedCards.forEach((cardGroup, pageIndex) => {
        printHTML += `
            <div class="print-page">
                <div class="print-cards-grid">
                    ${cardGroup.join('')}
                </div>
                <div class="page-number">${pageIndex + 1}</div>
            </div>
        `;
    });

    printHTML += `
        </body>
        </html>
    `;

    // Открываем окно для печати
    const printWindow = window.open('', '_blank', 'width=1200,height=800,scrollbars=yes');
    if (!printWindow) {
        console.error('Could not open print window');
        window.print();
        return;
    }

    printWindow.document.write(printHTML);
    printWindow.document.close();

    // Даем время на загрузку
    setTimeout(() => {
        console.log('Printing...');
        printWindow.print();

        // Закрываем окно после печати
        setTimeout(() => {
            if (!printWindow.closed) {
                printWindow.close();
            }
        }, 1000);
    }, 1000);
}

/**
 * Функция для поиска даты на странице
 */
function findDateOnPage() {
    // Способ 1: Из заголовка
    const dateHeader = document.querySelector('.timetable-current-date strong');
    if (dateHeader) {
        return dateHeader.textContent.trim();
    }

    // Способ 2: Из скрытого поля
    const hiddenDate = document.querySelector('input[name="date"]');
    if (hiddenDate && hiddenDate.value) {
        const dateValue = hiddenDate.value;
        const parts = dateValue.split('-');
        if (parts.length === 3) {
            return `${parts[2]}.${parts[1]}.${parts[0]}`;
        }
    }

    return null;
}

/**
 * Инициализация обработчиков для печати
 */
function initializePrintHandlers() {
    console.log('Initializing print handlers...');

    // Обработка нажатия Ctrl+P
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
            e.preventDefault();
            printSchedule();
        }
    });

    // Делаем функцию глобально доступной
    window.printSchedule = printSchedule;
}

// Инициализируем при загрузке документа
document.addEventListener('DOMContentLoaded', initializePrintHandlers);