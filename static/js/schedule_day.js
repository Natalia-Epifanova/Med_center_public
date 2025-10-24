document.addEventListener('DOMContentLoaded', function() {
    // Обработка формы комментария дня
    const dayCommentForm = document.getElementById('dayCommentForm');
    if (dayCommentForm) {
        dayCommentForm.addEventListener('submit', function(e) {
            e.preventDefault();

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
                console.error('Error:', error);
                showAlert('Ошибка при сохранении комментария', 'danger');
            });
        });
    }

    function showAlert(message, type) {
        // Создаем и показываем alert
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Вставляем в начало контента
        const content = document.querySelector('.container');
        content.insertBefore(alertDiv, content.firstChild);

        // Автоматически скрываем через 5 секунд
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
});