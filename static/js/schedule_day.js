console.log('=== SCHEDULE_DAY.JS LOADED SUCCESSFULLY ===');

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded - Initializing schedule day functionality');
    console.log('Bootstrap available:', typeof bootstrap !== 'undefined');

    // Проверка блокировки слотов при клике
    initSlotLockChecks();

    // Инициализация выпадающих списков статусов
    initStatusSelects();

    // Инициализация кнопок удаления всех слотов
    initDeleteButtons();

    // Инициализация формы выбора даты
    initDateForm();

    // Инициализация формы комментария дня
    initDayCommentForm();

    // Инициализация управления прокруткой
    initScrollControls(); // <-- ДОБАВЛЕНО
});

// ============ ИНИЦИАЛИЗАЦИЯ КНОПОК УДАЛЕНИЯ ВСЕХ СЛОТОВ ============
function initDeleteButtons() {
    console.log('Initializing delete buttons...');

    // Обработка удаления всех слотов врача
    document.querySelectorAll('.delete-all-slots-btn').forEach(button => {
        console.log('Found delete button for doctor:', button.dataset.doctorName || 'Unknown');
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();

            const doctorId = this.dataset.doctorId;
            const cabinetId = this.dataset.cabinetId;
            const date = this.dataset.date;
            const doctorName = this.dataset.doctorName;
            const cabinetNumber = this.dataset.cabinetNumber;

            console.log('Delete button clicked:', {
                doctorId,
                cabinetId,
                date,
                doctorName,
                cabinetNumber
            });

            // Заполняем модальное окно
            const doctorNameDisplay = document.getElementById('doctorNameDisplay');
            const cabinetNumberDisplay = document.getElementById('cabinetNumberDisplay');
            const dateDisplay = document.getElementById('dateDisplay');

            if (doctorNameDisplay) doctorNameDisplay.textContent = doctorName || 'Неизвестный врач';
            if (cabinetNumberDisplay) cabinetNumberDisplay.textContent = cabinetNumber || 'Неизвестный кабинет';
            if (dateDisplay) dateDisplay.textContent = date || 'Неизвестная дата';

            // Сохраняем данные для удаления
            const modal = document.getElementById('deleteAllSlotsModal');
            if (modal) {
                modal.dataset.doctorId = doctorId;
                modal.dataset.cabinetId = cabinetId;
                modal.dataset.date = date;

                // Показываем модальное окно
                try {
                    const bsModal = new bootstrap.Modal(modal);
                    bsModal.show();
                } catch (error) {
                    console.error('Error showing modal:', error);
                    showNotification('Ошибка открытия окна подтверждения', 'error');
                }
            } else {
                console.error('Delete modal not found!');
            }
        });
    });

    // Обработка подтверждения удаления
    const confirmDeleteBtn = document.getElementById('confirmDeleteAllBtn');
    if (confirmDeleteBtn) {
        console.log('Found confirm delete button');
        confirmDeleteBtn.addEventListener('click', function() {
            console.log('Confirm delete clicked');
            const modal = document.getElementById('deleteAllSlotsModal');
            if (modal) {
                const doctorId = modal.dataset.doctorId;
                const cabinetId = modal.dataset.cabinetId;
                const date = modal.dataset.date;

                console.log('Deleting slots with data:', { doctorId, cabinetId, date });

                if (doctorId && cabinetId && date) {
                    // Отправляем запрос на удаление
                    deleteAllDoctorSlots(doctorId, cabinetId, date);

                    // Закрываем модальное окно
                    try {
                        const bsModal = bootstrap.Modal.getInstance(modal);
                        if (bsModal) bsModal.hide();
                    } catch (error) {
                        console.error('Error hiding modal:', error);
                    }
                } else {
                    console.error('Missing data for deletion:', { doctorId, cabinetId, date });
                    showNotification('Ошибка: недостаточно данных для удаления', 'error');
                }
            } else {
                console.error('Delete modal not found!');
                showNotification('Ошибка: не найдено окно подтверждения', 'error');
            }
        });
    } else {
        console.log('Confirm delete button NOT FOUND');
    }
}

function deleteAllDoctorSlots(doctorId, cabinetId, date) {
    const csrfToken = getCSRFToken();
    console.log('CSRF Token for delete:', csrfToken ? 'Available' : 'Missing');

    if (!csrfToken) {
        showNotification('Ошибка безопасности: CSRF токен не найден', 'error');
        return;
    }

    // Показываем индикатор загрузки
    showNotification('Удаление слотов...', 'info');

    // Подготовка данных
    const requestData = {
        doctor_id: parseInt(doctorId),
        cabinet_id: parseInt(cabinetId),
        date: date
    };

    console.log('Sending delete request with data:', requestData);

    fetch('/timetable/delete-all-doctor-slots/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(requestData),
        credentials: 'same-origin'
    })
    .then(response => {
        console.log('Delete response status:', response.status);
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(`HTTP ${response.status}: ${text}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Delete response data:', data);
        if (data.success) {
            showNotification(`Успешно удалено ${data.deleted_count} слотов`, 'success');
            // Перезагружаем страницу через 1 секунду
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showNotification('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
        }
    })
    .catch(error => {
        console.error('Delete error:', error);
        showNotification('Ошибка соединения: ' + error.message, 'error');
    });
}

// ============ ПРОВЕРКА БЛОКИРОВКИ СЛОТОВ ============
function initSlotLockChecks() {
    document.querySelectorAll('.check-slot-lock').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const slotId = this.dataset.slotId;
            const url = this.href;

            // Проверяем блокировку через AJAX
            fetch(`/appointments/check-slot-lock/${slotId}/`, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.is_locked) {
                    // Слот заблокирован - показываем сообщение
                    alert(`Этот слот заблокирован администратором ${data.locked_by}.\nПожалуйста, попробуйте позже.`);
                } else {
                    // Слот свободен - переходим к созданию записи
                    window.location.href = url;
                }
            })
            .catch(error => {
                console.error('Ошибка проверки блокировки:', error);
                // В случае ошибки все равно переходим
                window.location.href = url;
            });
        });
    });
}

// ============ ВЫПАДАЮЩИЕ СПИСКИ СТАТУСОВ ============
function initStatusSelects() {
    // Инициализируем стили для всех выпадающих списков при загрузке
    initializeStatusSelectStyles();

    // Обработка изменения статуса записи
    const statusSelects = document.querySelectorAll('.appointment-status-select');
    console.log('Found status select elements:', statusSelects.length);

    statusSelects.forEach((select, index) => {
        console.log(`Initializing select ${index + 1} for appointment:`, select.dataset.appointmentId);

        // Устанавливаем начальный стиль
        updateStatusSelectStyle(select, select.value);

        select.addEventListener('change', function() {
            const appointmentId = this.dataset.appointmentId;
            const newStatus = this.value;

            console.log(`Status changed for appointment ${appointmentId}:`, newStatus);
            updateAppointmentStatus(appointmentId, newStatus, this);
        });
    });
}

function initializeStatusSelectStyles() {
    const statusSelects = document.querySelectorAll('.appointment-status-select');
    statusSelects.forEach(select => {
        updateStatusSelectStyle(select, select.value);
    });
}

function updateAppointmentStatus(appointmentId, newStatus, element) {
    const csrfToken = getCSRFToken();
    console.log('CSRF Token:', csrfToken ? 'Available' : 'Missing');

    // Показываем индикатор загрузки
    const originalValue = element.value;
    element.disabled = true;
    element.classList.add('loading');

    // Временно меняем стиль для мгновенной обратной связи
    updateStatusSelectStyle(element, newStatus);

    // Используем FormData для правильной работы с CSRF
    const formData = new FormData();
    formData.append('status', newStatus);
    formData.append('csrfmiddlewaretoken', csrfToken);

    console.log(`Sending request to update appointment ${appointmentId} to status: ${newStatus}`);

    fetch(`/appointments/${appointmentId}/update-status/`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData
    })
    .then(response => {
        console.log('Response status:', response.status);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Response data:', data);
        if (data.success) {
            showNotification(`Статус изменен на: ${data.new_status_display}`, 'success');

            // Обновляем стиль окончательно
            updateStatusSelectStyle(element, newStatus);
            element.value = newStatus;

            console.log('Status updated successfully - no page reload');
        } else {
            console.error('Server returned error:', data.error);
            showNotification('Ошибка при изменении статуса: ' + data.error, 'error');
            // Возвращаем предыдущее значение и стиль
            element.value = originalValue;
            updateStatusSelectStyle(element, originalValue);
        }
    })
    .catch(error => {
        console.error('Fetch error:', error);
        showNotification('Ошибка соединения: ' + error.message, 'error');
        // Возвращаем предыдущее значение и стиль
        element.value = originalValue;
        updateStatusSelectStyle(element, originalValue);
    })
    .finally(() => {
        element.disabled = false;
        element.classList.remove('loading');
    });
}

function updateStatusSelectStyle(selectElement, status) {
    if (!selectElement) return;

    // Удаляем все классы статусов
    selectElement.classList.remove(
        'status-scheduled', 'status-confirmed', 'status-completed',
        'status-cancelled', 'status-no_show', 'status-default',
        'border-primary', 'border-info', 'border-success',
        'border-warning', 'border-danger', 'text-muted'
    );

    // Добавляем базовый класс и класс в зависимости от статуса
    selectElement.classList.add('status-' + status);

    // Добавляем классы Bootstrap для границ
    switch(status) {
        case 'scheduled':
            selectElement.classList.add('border-primary', 'bg-primary-light');
            break;
        case 'confirmed':
            selectElement.classList.add('border-info', 'bg-info-light');
            break;
        case 'completed':
            selectElement.classList.add('border-success', 'bg-success-light');
            break;
        case 'cancelled':
            selectElement.classList.add('border-warning', 'bg-warning-light');
            break;
        case 'no_show':
            selectElement.classList.add('border-danger', 'bg-danger-light');
            break;
        default:
            selectElement.classList.add('border-secondary', 'bg-light');
    }
}

// ============ ФОРМА ВЫБОРА ДАТЫ ============
function initDateForm() {
    // Автоматическая отправка формы при изменении даты
    const dateInput = document.getElementById('date');
    if (dateInput) {
        dateInput.addEventListener('change', function() {
            console.log('Date changed, submitting form');
            this.form.submit();
        });
    }
}

// ============ ФОРМА КОММЕНТАРИЯ ДНЯ ============
function initDayCommentForm() {
    // Обработка формы комментария дня
    const dayCommentForm = document.getElementById('dayCommentForm');
    if (dayCommentForm) {
        console.log('Day comment form found, adding event listener');
        dayCommentForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Day comment form submitted');

            const formData = new FormData(this);

            fetch(this.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            })
            .then(response => response.json())
            .then(data => {
                console.log('Day comment response:', data);
                if (data.success) {
                    // Закрываем модальное окно
                    const modalElement = document.getElementById('dayCommentModal');
                    if (modalElement) {
                        const modal = bootstrap.Modal.getInstance(modalElement);
                        if (modal) modal.hide();
                    }

                    // Показываем сообщение об успехе
                    showAlert('Комментарий успешно сохранен', 'success');

                    // Перезагружаем страницу через секунду
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    showAlert('Ошибка: ' + data.error, 'danger');
                }
            })
            .catch(error => {
                console.error('Day comment error:', error);
                showAlert('Ошибка при сохранении комментария', 'danger');
            });
        });
    } else {
        console.log('Day comment form not found');
    }
}

// ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============
function getCSRFToken() {
    // Ищем CSRF токен в куках (основной способ в Django)
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, 10) === 'csrftoken=') {
                cookieValue = decodeURIComponent(cookie.substring(10));
                break;
            }
        }
    }

    // Если не нашли в куках, ищем в скрытом поле
    if (!cookieValue) {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) {
            cookieValue = csrfInput.value;
        }
    }

    return cookieValue;
}

function showNotification(message, type) {
    console.log(`Showing notification: ${message} (${type})`);

    // Создаем уведомление
    const alertClass = type === 'success' ? 'alert-success' :
                      type === 'info' ? 'alert-info' :
                      type === 'warning' ? 'alert-warning' : 'alert-danger';
    const icon = type === 'success' ? 'fa-check-circle' :
                type === 'info' ? 'fa-info-circle' :
                type === 'warning' ? 'fa-exclamation-triangle' : 'fa-exclamation-triangle';

    const notification = document.createElement('div');
    notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px; max-width: 400px;';
    notification.innerHTML = `
        <i class="fas ${icon} me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(notification);

    // Автоматическое скрытие через 3 секунды
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 3000);
}

function showAlert(message, type) {
    console.log(`Showing alert: ${message} (${type})`);

    // Создаем и показываем alert
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    // Вставляем в начало контента
    const content = document.querySelector('.container');
    if (content) {
        content.insertBefore(alertDiv, content.firstChild);
    } else {
        document.body.insertBefore(alertDiv, document.body.firstChild);
    }

    // Автоматически скрываем через 5 секунд
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}
// ============ УПРАВЛЕНИЕ ПРОКРУТКОЙ КАБИНЕТОВ ============
function initScrollControls() {
    console.log('Initializing scroll controls...');

    const scrollContainer = document.querySelector('.timetable-cards-scroll-container');
    const scrollLeftBtn = document.querySelector('.scroll-left-btn');
    const scrollRightBtn = document.querySelector('.scroll-right-btn');

    if (!scrollContainer || !scrollLeftBtn || !scrollRightBtn) {
        console.log('Scroll controls not found');
        return;
    }

    const scrollAmount = 400; // Количество пикселей для прокрутки

    // Кнопка "Влево"
    scrollLeftBtn.addEventListener('click', function() {
        scrollContainer.scrollBy({
            left: -scrollAmount,
            behavior: 'smooth'
        });
    });

    // Кнопка "Вправо"
    scrollRightBtn.addEventListener('click', function() {
        scrollContainer.scrollBy({
            left: scrollAmount,
            behavior: 'smooth'
        });
    });

    // Обновление состояния кнопок при прокрутке
    scrollContainer.addEventListener('scroll', function() {
        updateScrollButtonsState(scrollContainer);
    });

    // Инициализируем состояние кнопок
    updateScrollButtonsState(scrollContainer);

    console.log('Scroll controls initialized');
}

function updateScrollButtonsState(scrollContainer) {
    const scrollLeftBtn = document.querySelector('.scroll-left-btn');
    const scrollRightBtn = document.querySelector('.scroll-right-btn');

    if (!scrollLeftBtn || !scrollRightBtn) return;

    // Кнопка "Влево" активна, если есть прокрутка слева
    scrollLeftBtn.disabled = scrollContainer.scrollLeft <= 0;

    // Кнопка "Вправо" активна, если есть прокрутка справа
    scrollRightBtn.disabled =
        scrollContainer.scrollLeft + scrollContainer.clientWidth >= scrollContainer.scrollWidth - 1;

    // Обновляем стили
    if (scrollLeftBtn.disabled) {
        scrollLeftBtn.classList.add('disabled');
        scrollLeftBtn.style.opacity = '0.5';
    } else {
        scrollLeftBtn.classList.remove('disabled');
        scrollLeftBtn.style.opacity = '1';
    }

    if (scrollRightBtn.disabled) {
        scrollRightBtn.classList.add('disabled');
        scrollRightBtn.style.opacity = '0.5';
    } else {
        scrollRightBtn.classList.remove('disabled');
        scrollRightBtn.style.opacity = '1';
    }
}

console.log('=== SCHEDULE_DAY.JS INITIALIZATION COMPLETE ===');