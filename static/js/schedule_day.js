console.log('=== SCHEDULE_DAY.JS LOADED SUCCESSFULLY ===');

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded - Initializing schedule day functionality');

    // Инициализируем стили для всех выпадающих списков при загрузке
    initializeStatusSelectStyles();

    // Автоматическая отправка формы при изменении даты
    const dateInput = document.getElementById('date');
    if (dateInput) {
        dateInput.addEventListener('change', function() {
            console.log('Date changed, submitting form');
            this.form.submit();
        });
    }

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
                // УБИРАЕМ перезагрузку страницы - изменения сохраняются в БД

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
        const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
        const icon = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-triangle';

        const notification = document.createElement('div');
        notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
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

    // Обработка формы комментария дня (оставляем как есть)
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
                    const modal = bootstrap.Modal.getInstance(document.getElementById('dayCommentModal'));
                    modal.hide();

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
});

console.log('=== SCHEDULE_DAY.JS INITIALIZATION COMPLETE ===');