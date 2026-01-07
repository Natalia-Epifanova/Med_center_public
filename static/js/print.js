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
                    cardTitle.innerHTML = `<strong style="font-size: 10pt;">${cabinetMatch[0]}</strong>`;
                }
            }
        }

        // 2. Убираем комментарий кабинета из печати
        const cabinetCommentSection = clonedCard.querySelector('.cabinet-comment-section');
        if (cabinetCommentSection) {
            cabinetCommentSection.style.display = 'none';
        }

        // 3. Правильно обрабатываем заголовки врачей
        const doctorHeaders = clonedCard.querySelectorAll('.doctor-header');
        doctorHeaders.forEach(header => {
            // Сохраняем оригинальное содержимое
            const originalHTML = header.innerHTML;

            // Ищем ФИО врача (пробуем несколько вариантов)
            let doctorName = '';
            let doctorSpecialization = '';
            let doctorComment = '';

            // Вариант 1: Ищем в текстовых элементах
            const textElements = header.querySelectorAll('*');
            textElements.forEach(el => {
                const text = el.textContent.trim();

                // Ищем ФИО в формате "Фамилия И.О."
                if (!doctorName && text.match(/[А-Я][а-я]+\s+[А-Я]\.\s*[А-Я]\./)) {
                    doctorName = text.match(/[А-Я][а-я]+\s+[А-Я]\.\s*[А-Я]\./)[0];
                }

                // Ищем специализацию (текст темного цвета)
                if (!doctorSpecialization && el.classList.contains('text-dark')) {
                    doctorSpecialization = text;
                }

                // Ищем комментарий (текст красного цвета)
                if (!doctorComment && el.classList.contains('text-danger')) {
                    doctorComment = text;
                }

                // Ищем просто ФИО без формата
                if (!doctorName && text.split(' ').length >= 2 && text.length < 50) {
                    // Проверяем, не является ли это номером телефона или другим текстом
                    if (!text.includes('+7') && !text.includes('рублей') && !text.includes('карта')) {
                        doctorName = text;
                    }
                }
            });

            // Вариант 2: Ищем в исходной карточке
            if (!doctorName || !doctorSpecialization) {
                const originalHeader = card.querySelector('.doctor-header');
                if (originalHeader) {
                    // Ищем ФИО
                    const nameElements = originalHeader.querySelectorAll('.text-primary, strong');
                    nameElements.forEach(el => {
                        const text = el.textContent.trim();
                        if (!doctorName && text.match(/[А-Я]/)) {
                            doctorName = text;
                        }
                    });

                    // Ищем специализацию
                    const specElements = originalHeader.querySelectorAll('.text-dark, .doctor-specialization');
                    specElements.forEach(el => {
                        const text = el.textContent.trim();
                        if (!doctorSpecialization && text && text.length > 2) {
                            doctorSpecialization = text;
                        }
                    });

                    // Ищем комментарий
                    const commentElements = originalHeader.querySelectorAll('.text-danger');
                    commentElements.forEach(el => {
                        const text = el.textContent.trim();
                        if (!doctorComment && text) {
                            doctorComment = text;
                        }
                    });
                }
            }

            // Очищаем header и добавляем информацию врача
            header.innerHTML = '';
            header.style.cssText = 'padding: 1.5mm; margin-bottom: 1mm; font-size: 8pt; text-align: center; background-color: #ffffcc; border: 0.5px solid #ccc; border-radius: 1mm;';

            // Добавляем ФИО врача
            if (doctorName) {
                const nameDiv = document.createElement('div');
                nameDiv.innerHTML = `<strong style="font-size: 9pt;">${doctorName}</strong>`;
                header.appendChild(nameDiv);
            }

            // Добавляем специализацию
            if (doctorSpecialization) {
                const specDiv = document.createElement('div');
                specDiv.innerHTML = `<span style="font-size: 8pt; font-weight: bold;">${doctorSpecialization}</span>`;
                header.appendChild(specDiv);
            }

            // Добавляем комментарий врача (черным цветом)
            if (doctorComment) {
                const commentDiv = document.createElement('div');
                commentDiv.innerHTML = `<span style="font-size: 8pt; font-weight: bold; color: black !important; margin-top: 0.5mm; display: block;">${doctorComment}</span>`;
                header.appendChild(commentDiv);
            }

            // Убираем кнопку "Удалить все слоты"
            const deleteButton = header.querySelector('.delete-all-slots-btn');
            if (deleteButton) deleteButton.remove();
        });

        // 4. Убираем кнопки действий и связанные элементы
        const actionCells = clonedCard.querySelectorAll('.timetable-table-sm td:nth-child(5)');
        actionCells.forEach(cell => cell.style.display = 'none');

        const actionHeaders = clonedCard.querySelectorAll('.timetable-table-sm th:nth-child(5)');
        actionHeaders.forEach(header => header.style.display = 'none');

        // 5. Преобразуем время - оставляем только начало
        const timeCells = clonedCard.querySelectorAll('.timetable-table-sm td:nth-child(1)');
        timeCells.forEach(cell => {
            // Обрабатываем все strong элементы с временем
            const strongElements = cell.querySelectorAll('strong');
            strongElements.forEach(el => {
                const timeText = el.textContent || el.innerText;
                if (timeText.includes('-')) {
                    const startTime = timeText.split('-')[0];
                    el.textContent = startTime.trim();
                    el.style.fontSize = '7pt';
                    el.style.fontWeight = 'bold';
                }
            });

            // Убираем "Перерыв" и комментарии
            const breakText = cell.querySelector('.text-muted.fw-bold');
            if (breakText) breakText.remove();

            const descriptionText = cell.querySelector('small.text-dark.fw-bold');
            if (descriptionText) descriptionText.remove();

            // Убираем бейджи типов оплаты
            const badge = cell.querySelector('.badge');
            if (badge) badge.remove();

            // Убираем все ссылки
            const links = cell.querySelectorAll('a');
            links.forEach(link => {
                const timeText = link.textContent || link.innerText;
                if (timeText.includes('-')) {
                    const startTime = timeText.split('-')[0];
                    const timeSpan = document.createElement('span');
                    timeSpan.innerHTML = `<strong style="font-size: 7pt; font-weight: bold;">${startTime.trim()}</strong>`;
                    link.parentNode.replaceChild(timeSpan, link);
                }
            });
        });

        // 6. ВОССТАНАВЛИВАЕМ ДАННЫЕ ПАЦИЕНТОВ ИЗ ОРИГИНАЛЬНОЙ КАРТОЧКИ
        // Находим все строки таблицы в оригинальной карточке
        const originalRows = card.querySelectorAll('.timetable-table-sm tbody tr');
        const clonedRows = clonedCard.querySelectorAll('.timetable-table-sm tbody tr');

        // Проходим по всем строкам и копируем данные пациентов
        originalRows.forEach((originalRow, rowIndex) => {
            const clonedRow = clonedRows[rowIndex];
            if (clonedRow) {
                // Ищем данные пациента в оригинальной строке (3-я ячейка)
                const originalPatientCell = originalRow.querySelector('td:nth-child(3)');
                const clonedPatientCell = clonedRow.querySelector('td:nth-child(3)');

                if (originalPatientCell && clonedPatientCell) {
                    // Получаем все содержимое ячейки с пациентом
                    const patientContent = originalPatientCell.innerHTML.trim();

                    if (patientContent && patientContent !== '-') {
                        // Упрощаем обработку: берем весь текст и убираем лишнее
                        let patientText = originalPatientCell.textContent || originalPatientCell.innerText;
                        patientText = patientText.trim();

                        // Удаляем номера телефонов
                        patientText = patientText.replace(/\+7\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}/g, '');

                        // Удаляем информацию о картах
                        patientText = patientText.replace(/карта\s*\d+/gi, '');
                        patientText = patientText.replace(/ОМС\s*карта\s*\d+/gi, '');
                        patientText = patientText.replace(/ИП\s*карта\s*\d+/gi, '');
                        patientText = patientText.replace(/\(\s*\)/g, '');

                        // Очищаем от лишних пробелов
                        patientText = patientText.replace(/\s+/g, ' ').trim();

                        // Разделяем по переводам строк и берем первую строку
                        const lines = patientText.split('\n');
                        let finalText = lines[0] || patientText;

                        // Если есть тег <strong>, берем только его содержимое
                        const strongElement = originalPatientCell.querySelector('strong');
                        if (strongElement) {
                            finalText = strongElement.textContent.trim();
                        }

                        // Ограничиваем длину текста
                        if (finalText.length > 30) {
                            finalText = finalText.substring(0, 27) + '...';
                        }

                        // Записываем в клонированную ячейку
                        if (finalText && finalText !== '-') {
                            clonedPatientCell.innerHTML = `<strong style="font-size: 7pt;">${finalText}</strong>`;
                        } else {
                            clonedPatientCell.innerHTML = '<strong style="font-size: 7pt;">-</strong>';
                        }
                    } else {
                        clonedPatientCell.innerHTML = '<strong style="font-size: 7pt;">-</strong>';
                    }
                }
            }
        });

        // 7. Обработка ссылок в других ячейках
        const otherLinks = clonedCard.querySelectorAll('a');
        otherLinks.forEach(link => {
            const text = link.textContent || link.innerText;
            link.parentNode.replaceChild(document.createTextNode(text), link);
        });

        // 8. Убираем пустые строки
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

    // Создаем HTML для печати
    let printHTML = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Расписание на ${scheduleDate}</title>
            <meta charset="UTF-8">
            <style>
                /* ОСНОВНЫЕ СТИЛИ */
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }

                /* РАЗМЕР СТРАНИЦЫ */
                @page {
                    size: A4 landscape;
                    margin: 20mm 15mm 8mm 8mm !important;
                }

                /* СТИЛИ ДЛЯ ПЕЧАТИ */
                @media print {
                    body {
                        margin: 0 !important;
                        padding: 10mm 0 0 0 !important;
                        width: 100% !important;
                        font-size: 7pt !important;
                        font-family: Arial, sans-serif !important;
                        color: black !important;
                        background: white !important;
                    }
                }

                body {
                    margin: 0;
                    padding: 10mm 0 0 0 !important;
                    font-family: Arial, sans-serif;
                    font-size: 7pt;
                    background: white;
                    color: black;
                }

                .print-page {
                    width: 100%;
                    margin: 0 auto;
                    padding: 0;
                    page-break-after: always;
                }

                /* СЕТКА КАРТОЧЕК */
                .print-cards-grid {
                    display: grid !important;
                    grid-template-columns: repeat(3, 1fr) !important;
                    gap: 1.5mm !important;
                    width: 95% !important;
                    max-width: 95% !important;
                    margin: 0 auto !important;
                    padding: 0 !important;
                }

                /* КАРТОЧКА КАБИНЕТА */
                .print-cabinet-card {
                    border: 0.5px solid #000 !important;
                    border-radius: 0.5mm;
                    overflow: hidden;
                    page-break-inside: avoid;
                    break-inside: avoid;
                    height: 165mm !important;
                    display: flex;
                    flex-direction: column;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                .print-cabinet-header {
                    background-color: #f0f0f0 !important;
                    color: black !important;
                    padding: 0.8mm 1mm !important;
                    text-align: center;
                    font-size: 9pt !important;
                    font-weight: bold;
                    border-bottom: 0.5px solid #000 !important;
                }

                .print-cabinet-body {
                    padding: 0.8mm !important;
                    flex-grow: 1;
                    overflow: hidden;
                    font-size: 7pt !important;
                }

                /* ТАБЛИЦА */
                table {
                    width: 100% !important;
                    border-collapse: collapse !important;
                    font-size: 7pt !important;
                    table-layout: fixed !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                table th {
                    background-color: #f8f8f8 !important;
                    border: 0.5px solid #ccc !important;
                    padding: 0.4mm 0.5mm !important;
                    text-align: left;
                    font-weight: bold;
                    height: 4.5mm;
                    font-size: 7pt !important;
                }

                table td {
                    border: 0.5px solid #ccc !important;
                    padding: 0.3mm 0.4mm !important;
                    vertical-align: top;
                    height: 3.8mm;
                    font-size: 7pt !important;
                    line-height: 1.1 !important;
                    word-break: break-word !important;
                    overflow-wrap: break-word !important;
                }

                table tr:nth-child(even) {
                    background-color: #fafafa !important;
                }

                /* ШИРИНЫ КОЛОНОК */
                table th:nth-child(1),
                table td:nth-child(1) {
                    width: 9% !important;
                    font-size: 7pt !important;
                    font-weight: bold !important;
                }

                table th:nth-child(2),
                table td:nth-child(2) {
                    width: 22% !important;
                    font-size: 7pt !important;
                    word-break: break-word !important;
                }

                table th:nth-child(3),
                table td:nth-child(3) {
                    width: 24% !important;
                    font-size: 7pt !important;
                    word-break: break-word !important;
                    overflow-wrap: break-word !important;
                }

                table th:nth-child(4),
                table td:nth-child(4) {
                    width: 18% !important;
                    font-size: 7pt !important;
                    word-break: break-word !important;
                    overflow-wrap: break-word !important;
                }

                /* Скрываем колонку действий */
                table th:nth-child(5),
                table td:nth-child(5) {
                    display: none !important;
                }

                /* ЗАГОЛОВОК ВРАЧА */
                .doctor-header {
                    background-color: #ffffcc !important;
                    border: 0.5px solid #ffcc00 !important;
                    border-radius: 0.8mm !important;
                    padding: 1mm !important;
                    margin: 0.5mm 0 !important;
                    text-align: center !important;
                    font-size: 8pt !important;
                    font-weight: bold !important;
                }

                .doctor-header strong {
                    font-size: 9pt !important;
                }

                .doctor-header span {
                    font-size: 8pt !important;
                    color: black !important;
                }

                /* Убираем все ссылки */
                a {
                    color: black !important;
                    text-decoration: none !important;
                }

                strong {
                    font-size: 7pt !important;
                }

                /* НОМЕР СТРАНИЦЫ */
                .page-number {
                    position: fixed;
                    bottom: 2mm;
                    right: 4mm;
                    font-size: 7pt;
                    color: #666;
                }

                /* Скрываем ненужные элементы */
                .no-print,
                .cabinet-comment-section {
                    display: none !important;
                }
            </style>
        </head>
        <body>
    `;

    // Добавляем каждую страницу
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