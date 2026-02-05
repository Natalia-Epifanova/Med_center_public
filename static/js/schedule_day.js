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

    initCabinetComments(); // <-- Добавьте эту строку

    initPaymentMethods(); // <-- Добавьте эту строку

    initMoveDoctorButtons(); // <-- Добавьте эту строку
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
// ============ ПЕРЕНОС ВРАЧА В ДРУГОЙ КАБИНЕТ ============
function initMoveDoctorButtons() {
    console.log('Initializing move doctor buttons...');

    // Обработка кнопки переноса врача
    document.querySelectorAll('.move-doctor-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();

            const doctorId = this.dataset.doctorId;
            const currentCabinetId = this.dataset.cabinetId;
            const date = this.dataset.date;
            const doctorName = this.dataset.doctorName;
            const currentCabinetNumber = this.dataset.currentCabinet;

            console.log('Move doctor clicked:', {
                doctorId,
                currentCabinetId,
                date,
                doctorName,
                currentCabinetNumber
            });

            // Заполняем модальное окно
            document.getElementById('moveDoctorId').value = doctorId;
            document.getElementById('moveCurrentCabinetId').value = currentCabinetId;
            document.getElementById('moveDate').value = date;
            document.getElementById('moveDoctorName').textContent = doctorName || 'Неизвестный врач';
            document.getElementById('moveCurrentCabinetNumber').textContent = currentCabinetNumber || 'Неизвестный кабинет';
            document.getElementById('moveDateDisplay').textContent = date || 'Неизвестная дата';

            // Исключаем текущий кабинет из списка
            const select = document.getElementById('newCabinet');
            if (select) {
                for (let i = 0; i < select.options.length; i++) {
                    if (select.options[i].value === currentCabinetId) {
                        select.options[i].disabled = true;
                    } else {
                        select.options[i].disabled = false;
                    }
                }
            }

            // Показываем модальное окно
            const modal = document.getElementById('moveDoctorModal');
            if (modal) {
                try {
                    const bsModal = new bootstrap.Modal(modal);
                    bsModal.show();
                } catch (error) {
                    console.error('Error showing move modal:', error);
                    showNotification('Ошибка открытия окна переноса', 'error');
                }
            }
        });
    });

    // Обработка формы переноса
    const moveDoctorForm = document.getElementById('moveDoctorForm');
    if (moveDoctorForm) {
        moveDoctorForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const moveAppointments = formData.get('move_appointments') === 'on';

            if (!confirm(`Вы уверены, что хотите перенести врача в другой кабинет? ${moveAppointments ? 'Все существующие записи пациентов также будут перенесены.' : 'Существующие записи пациентов останутся в старом кабинете и их нужно будет перенести вручную.'}`)) {
                return;
            }

            // Отправляем запрос на сервер
            moveDoctorToNewCabinet(formData);
        });
    }
}

function moveDoctorToNewCabinet(formData) {
    const csrfToken = getCSRFToken();

    if (!csrfToken) {
        showNotification('Ошибка безопасности: CSRF токен не найден', 'error');
        return;
    }

    // Добавляем CSRF токен в formData
    formData.append('csrfmiddlewaretoken', csrfToken);

    // Показываем индикатор загрузки
    showNotification('Проверка возможности переноса...', 'info');

    // Отправляем запрос
    fetch('/timetable/move-doctor-to-cabinet/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        }
    })
    .then(response => {
        return response.json().then(data => {
            return { status: response.status, ok: response.ok, data };
        });
    })
    .then(result => {
        console.log('Move doctor response:', result);

        if (result.data.success) {
            showNotification(
                `✅ Врач успешно перенесен! Слотов: ${result.data.slots_moved}, Записей: ${result.data.appointments_moved}`,
                'success'
            );

            // Закрываем модальное окно
            const modal = document.getElementById('moveDoctorModal');
            if (modal) {
                try {
                    const bsModal = bootstrap.Modal.getInstance(modal);
                    if (bsModal) bsModal.hide();
                } catch (error) {
                    console.error('Error hiding modal:', error);
                }
            }

            // Перезагружаем страницу через 1 секунду
            setTimeout(() => {
                window.location.reload();
            }, 1000);

        } else {
            // Простое сообщение об ошибке
            let errorMessage = result.data.error || 'Неизвестная ошибка';

            // Если это ошибка конфликтов
            if (errorMessage.includes('Обнаружены конфликты')) {
                errorMessage = '❌ Обнаружены конфликты в новом кабинете (пересекаются слоты)';
            }

            showNotification(errorMessage, 'error');
        }
    })
    .catch(error => {
        console.error('Move doctor error:', error);
        showNotification('Ошибка соединения с сервером', 'error');
    });
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

    // Показываем индикатор загрузки
    const originalValue = element.value;
    element.disabled = true;
    element.classList.add('loading');

    // Временно меняем стиль
    updateStatusSelectStyle(element, newStatus);

    const formData = new FormData();
    formData.append('status', newStatus);
    formData.append('csrfmiddlewaretoken', csrfToken);

    fetch(`/appointments/${appointmentId}/update-status/`, {
        method: 'POST',
        headers: {'X-Requested-With': 'XMLHttpRequest'},
        body: formData
    })
    .then(response => {
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            let message = `Статус изменен на: ${data.new_status_display}`;

            // Если была синхронизация с процедурной записью
            if (data.synced_procedural) {
                message += `\n✓ Статус также обновлен в процедурном кабинете (${data.synced_procedural.new_status_display})`;
            }

            showNotification(message, 'success');

            // Обновляем стиль
            updateStatusSelectStyle(element, newStatus);
            element.value = newStatus;

            // Если нужно, можно обновить статус и в процедурном кабинете на той же странице
            if (data.synced_procedural) {
                updateProceduralStatusOnPage(appointmentId, newStatus, data.synced_procedural.id);
            }

        } else {
            showNotification('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
            element.value = originalValue;
            updateStatusSelectStyle(element, originalValue);
        }
    })
    .catch(error => {
        console.error('Fetch error:', error);
        showNotification('Ошибка соединения: ' + error.message, 'error');
        element.value = originalValue;
        updateStatusSelectStyle(element, originalValue);
    })
    .finally(() => {
        element.disabled = false;
        element.classList.remove('loading');
    });
}

function updateProceduralStatusOnPage(mainAppointmentId, newStatus, proceduralAppointmentId) {
    // Находим select статуса для процедурной записи и обновляем его
    const proceduralSelect = document.querySelector(
        `.appointment-status-select[data-appointment-id="${proceduralAppointmentId}"]`
    );

    if (proceduralSelect && proceduralSelect.value !== newStatus) {
        proceduralSelect.value = newStatus;
        updateStatusSelectStyle(proceduralSelect, newStatus);

        // Можно показать небольшую анимацию
        proceduralSelect.parentElement.style.backgroundColor = '#e8f5e8';
        setTimeout(() => {
            proceduralSelect.parentElement.style.backgroundColor = '';
        }, 1000);
    }
}

function updateStatusSelectStyle(selectElement, status) {
    if (!selectElement) return;

    // Удаляем все классы статусов
    selectElement.classList.remove(
        'status-scheduled', 'status-confirmed', 'status-completed',
        'status-cancelled', 'status-no_show', 'status-default',
        'status-approached', 'status-in_room', 'status-not_called', 'status-no_reception', // ← ДОБАВЛЕНО
        'border-primary', 'border-info', 'border-success',
        'border-warning', 'border-danger', 'border-secondary',
        'text-muted', 'bg-primary-light', 'bg-info-light',
        'bg-success-light', 'bg-warning-light', 'bg-danger-light',
        'bg-light'
    );

    // Добавляем базовый класс и класс в зависимости от статуса
    selectElement.classList.add('status-' + status);

    // Добавляем классы Bootstrap для границ и фона
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
        case 'approached':
            selectElement.classList.add('border-info', 'bg-info-light'); // Синий для "Подошел"
            break;
        case 'in_room':
            selectElement.classList.add('border-info', 'bg-info-light'); // Синий для "Подошел"
            break;
        case 'not_called':
            selectElement.classList.add('border-warning', 'bg-warning-light'); // Желтый/оранжевый для "Не дозвонились"
            break;
        case 'no_show':
            selectElement.classList.add('border-danger', 'bg-danger-light'); // Красный для "Не явился"
            break;
        case 'no_reception':
            selectElement.classList.add('border-danger', 'bg-danger-light'); // Красный для "Не явился"
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
// ============ УПРАВЛЕНИЕ СПОСОБОМ ОПЛАТЫ ============
function initPaymentMethods() {
    console.log('Initializing payment methods...');

    // Инициализация - показываем способы оплаты для уже завершенных записей
    document.querySelectorAll('.payment-method-selector').forEach(selector => {
        const appointmentId = selector.dataset.appointmentId;
        const statusSelect = document.querySelector(`.appointment-status-select[data-appointment-id="${appointmentId}"]`);

        // Находим активную кнопку на сервере
        const activeCashBtn = selector.querySelector('.payment-method-btn[data-method="cash"].active-cash');
        const activeCardBtn = selector.querySelector('.payment-method-btn[data-method="card"].active-card');

        // Применяем стили сразу при загрузке
        if (activeCashBtn) {
            applyActiveStyle(activeCashBtn, 'cash');
        }
        if (activeCardBtn) {
            applyActiveStyle(activeCardBtn, 'card');
        }

        if (statusSelect && statusSelect.value === 'completed') {
            selector.classList.remove('d-none');
            selector.classList.add('show');
        }
    });

    // Обработка изменения статуса
    document.querySelectorAll('.appointment-status-select').forEach(select => {
        select.addEventListener('change', function() {
            const appointmentId = this.dataset.appointmentId;
            const newStatus = this.value;
            const paymentSelector = document.querySelector(`.payment-method-selector[data-appointment-id="${appointmentId}"]`);

            if (paymentSelector) {
                if (newStatus === 'completed') {
                    // Показываем с анимацией
                    paymentSelector.classList.remove('d-none');
                    setTimeout(() => {
                        paymentSelector.classList.add('show');
                    }, 10);
                } else {
                    // Скрываем с анимацией
                    paymentSelector.classList.remove('show');
                    setTimeout(() => {
                        paymentSelector.classList.add('d-none');
                    }, 300);
                }
            }
        });
    });

    // Обработка клика по кнопкам оплаты
    document.querySelectorAll('.payment-method-btn').forEach(button => {
        button.addEventListener('click', function() {
            const selector = this.closest('.payment-method-selector');
            const appointmentId = selector.dataset.appointmentId;
            const method = this.dataset.method;

            // НЕМЕДЛЕННО меняем визуальное состояние
            // Снимаем активные классы со всех кнопок
            const allButtons = selector.querySelectorAll('.payment-method-btn');
            allButtons.forEach(btn => {
                resetButtonStyle(btn);
            });

            // Применяем стиль к выбранной кнопке
            applyActiveStyle(this, method);

            // Отправляем на сервер
            updatePaymentMethod(appointmentId, method, this);
        });
    });
}

// Функция для применения активного стиля
function applyActiveStyle(button, method) {
    if (method === 'cash') {
        button.classList.add('active-cash');
        // Немедленно меняем стили
        button.style.backgroundColor = '#28a745';
        button.style.borderColor = '#28a745';
        button.style.color = 'white';
        button.style.boxShadow = '0 0 0 2px rgba(40, 167, 69, 0.25)';
        button.style.fontWeight = 'bold';
    } else if (method === 'card') {
        button.classList.add('active-card');
        // Немедленно меняем стили
        button.style.backgroundColor = '#17a2b8';
        button.style.borderColor = '#17a2b8';
        button.style.color = 'white';
        button.style.boxShadow = '0 0 0 2px rgba(23, 162, 184, 0.25)';
        button.style.fontWeight = 'bold';
    }
}

// Функция для сброса стилей кнопки
function resetButtonStyle(button) {
    button.classList.remove('active-cash', 'active-card');
    // Сбрасываем inline стили
    button.style.backgroundColor = '';
    button.style.borderColor = '';
    button.style.color = '';
    button.style.boxShadow = '';
    button.style.fontWeight = '';
}

function updatePaymentMethod(appointmentId, paymentMethod, buttonElement) {
    const csrfToken = getCSRFToken();

    if (!csrfToken) {
        showNotification('Ошибка безопасности', 'error');
        // Сбрасываем выделение при ошибке
        resetButtonStyle(buttonElement);
        return;
    }

    const formData = new FormData();
    formData.append('payment_method', paymentMethod);
    formData.append('csrfmiddlewaretoken', csrfToken);

    // Показываем индикатор загрузки
    const originalHtml = buttonElement.innerHTML;
    buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>';
    buttonElement.disabled = true;

    fetch(`/appointments/${appointmentId}/update-payment-method/`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showNotification(`Способ оплаты: ${data.payment_method_display}`, 'success');

            // Восстанавливаем кнопку с сохранением стиля
            const icon = paymentMethod === 'cash' ? 'fa-money-bill-wave' : 'fa-credit-card';
            const text = paymentMethod === 'cash' ? 'Нал' : 'Карта';
            buttonElement.innerHTML = `<i class="fas ${icon} me-1"></i>${text}`;
            buttonElement.disabled = false;

            // Убедимся, что стиль сохранился
            applyActiveStyle(buttonElement, paymentMethod);

        } else {
            showNotification('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
            // Сбрасываем выделение при ошибке
            resetButtonStyle(buttonElement);
            buttonElement.innerHTML = originalHtml;
            buttonElement.disabled = false;
        }
    })
    .catch(error => {
        console.error('Payment method update error:', error);
        showNotification('Ошибка соединения', 'error');
        // Сбрасываем выделение при ошибке
        resetButtonStyle(buttonElement);
        buttonElement.innerHTML = originalHtml;
        buttonElement.disabled = false;
    });
}

function resetPaymentButton(buttonElement, method, isSuccess = false) {
    const icon = method === 'cash' ? 'fa-money-bill-wave' : 'fa-credit-card';
    const text = method === 'cash' ? 'Нал' : 'Карта';

    buttonElement.innerHTML = `<i class="fas ${icon} me-1"></i>${text}`;
    buttonElement.disabled = false;

    if (!isSuccess) {
        // Сбрасываем выделение
        const allButtons = buttonElement.parentElement.querySelectorAll('.payment-method-btn');
        allButtons.forEach(btn => {
            if (btn.dataset.method === method) {
                btn.classList.remove('btn-success');
                btn.classList.add('btn-outline-secondary');
            }
        });
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

function showNotification(message, type, duration = 3000) {
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
    notification.style.cssText = `
        top: 20px;
        right: 20px;
        z-index: 1050;
        min-width: 300px;
        max-width: 600px;
        white-space: pre-line;
        max-height: 80vh;
        overflow-y: auto;
    `;

    notification.innerHTML = `
        <div class="d-flex align-items-start">
            <i class="fas ${icon} me-2 mt-1"></i>
            <div class="flex-grow-1">
                ${message}
            </div>
            <button type="button" class="btn-close ms-2" data-bs-dismiss="alert"></button>
        </div>
    `;

    document.body.appendChild(notification);

    // Автоматическое скрытие через указанное время
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, duration);
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
// ============ КОММЕНТАРИИ КАБИНЕТОВ ============
function initCabinetComments() {
    console.log('Initializing cabinet comments...');

    // Обработка кнопок редактирования
    document.querySelectorAll('.edit-cabinet-comment-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();

            const cabinetId = this.dataset.cabinetId;
            const cabinetNumber = this.dataset.cabinetNumber;
            const date = this.dataset.date;

            // Получаем текущий комментарий
            const commentSection = this.closest('.cabinet-comment-section');
            const commentContent = commentSection.querySelector('.cabinet-comment-content');
            let currentComment = '';

            if (commentContent && !commentContent.querySelector('.fst-italic')) {
                // Убираем HTML-разметку для текстового поля
                const commentText = commentContent.textContent;
                // Ищем первое вхождение "(записал" и обрезаем до него
                const createdByIndex = commentText.indexOf('(записал');
                if (createdByIndex !== -1) {
                    currentComment = commentText.substring(0, createdByIndex).trim();
                } else {
                    currentComment = commentText.trim();
                }
            }

            // Заполняем модальное окно
            const modal = document.getElementById('cabinetCommentModal');
            if (modal) {
                modal.querySelector('#cabinetNumberModal').textContent = cabinetNumber;
                modal.querySelector('#cabinetIdInput').value = cabinetId;
                modal.querySelector('#cabinetCommentTextarea').value = currentComment;

                // Сохраняем данные для отправки
                modal.dataset.cabinetId = cabinetId;
                modal.dataset.cabinetNumber = cabinetNumber;
                modal.dataset.currentComment = currentComment;

                // Показываем модальное окно
                try {
                    const bsModal = new bootstrap.Modal(modal);
                    bsModal.show();
                } catch (error) {
                    console.error('Error showing modal:', error);
                    showNotification('Ошибка открытия окна', 'error');
                }
            }
        });
    });

    // Обработка формы сохранения
    const cabinetCommentForm = document.getElementById('cabinetCommentForm');
    if (cabinetCommentForm) {
        cabinetCommentForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const cabinetId = formData.get('cabinet_id');
            const comment = formData.get('comment');

            fetch('/timetable/save-cabinet-comment/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Закрываем модальное окно
                    const modal = document.getElementById('cabinetCommentModal');
                    if (modal) {
                        const bsModal = bootstrap.Modal.getInstance(modal);
                        if (bsModal) bsModal.hide();
                    }

                    showNotification('Комментарий сохранен', 'success');
                    // Перезагружаем страницу через 1 секунду
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    showNotification('Ошибка: ' + data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Save cabinet comment error:', error);
                showNotification('Ошибка при сохранении', 'error');
            });
        });
    }

    // Обработка удаления комментария
    const deleteCabinetCommentBtn = document.getElementById('deleteCabinetCommentBtn');
    if (deleteCabinetCommentBtn) {
        deleteCabinetCommentBtn.addEventListener('click', function() {
            const modal = document.getElementById('cabinetCommentModal');
            if (modal) {
                const cabinetId = modal.querySelector('#cabinetIdInput').value;
                const date = modal.querySelector('[name="date"]').value;

                if (confirm('Удалить комментарий для этого кабинета?')) {
                    // Отправляем пустой комментарий для удаления
                    const formData = new FormData();
                    formData.append('cabinet_id', cabinetId);
                    formData.append('date', date);
                    formData.append('comment', '');
                    formData.append('csrfmiddlewaretoken', getCSRFToken());

                    fetch('/timetable/save-cabinet-comment/', {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                        }
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // Закрываем модальное окно
                            const bsModal = bootstrap.Modal.getInstance(modal);
                            if (bsModal) bsModal.hide();

                            showNotification('Комментарий удален', 'success');
                            // Перезагружаем страницу через 1 секунду
                            setTimeout(() => {
                                window.location.reload();
                            }, 1000);
                        } else {
                            showNotification('Ошибка удаления: ' + data.error, 'error');
                        }
                    })
                    .catch(error => {
                        console.error('Delete cabinet comment error:', error);
                        showNotification('Ошибка при удалении', 'error');
                    });
                }
            }
        });
    }
}
console.log('=== SCHEDULE_DAY.JS INITIALIZATION COMPLETE ===');