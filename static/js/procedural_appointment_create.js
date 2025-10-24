// Функция для форматирования номера телефона
function formatPhoneNumber(input) {
    let value = input.value.replace(/[^\d+]/g, '');

    if (!value.startsWith('+7') && value.length > 0) {
        if (value.startsWith('7') || value.startsWith('8')) {
            value = '+7' + value.slice(1);
        } else {
            value = '+7' + value;
        }
    }

    if (value.length > 12) {
        value = value.substring(0, 12);
    }

    input.value = value;
}

// Функция для заполнения дополнительной услуги
function populateAdditionalServices() {
    const additionalServiceSelect = document.getElementById('id_additional_service');
    const mainServiceSelect = document.getElementById('id_service');

    if (!additionalServiceSelect || !mainServiceSelect) return;

    additionalServiceSelect.innerHTML = '<option value="">---------</option>';

    const mainOptions = mainServiceSelect.querySelectorAll('option');
    mainOptions.forEach(option => {
        if (option.value !== '') {
            const newOption = document.createElement('option');
            newOption.value = option.value;
            newOption.textContent = option.textContent;
            additionalServiceSelect.appendChild(newOption);
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DEBUG: Procedural Appointment Form Loaded ===');

    const appointmentTypeRadios = document.querySelectorAll('input[name="appointment_type"]');
    const additionalServiceSection = document.getElementById('additionalServiceSection');
    const twoSlotsSection = document.getElementById('twoSlotsSection');
    const additionalServiceSelect = document.getElementById('id_additional_service');
    const serviceSelect = document.getElementById('id_service');
    const phoneInput = document.getElementById('id_phone_number');

    // Форматирование номера телефона
    if (phoneInput) {
        phoneInput.addEventListener('input', function() {
            formatPhoneNumber(this);
        });

        phoneInput.addEventListener('blur', function() {
            formatPhoneNumber(this);
        });

        if (phoneInput.value) {
            formatPhoneNumber(phoneInput);
        }
    }

    // Обработка изменения типа записи
    appointmentTypeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            console.log('Appointment type changed to:', this.value);

            // Сначала скрываем все секции
            if (additionalServiceSection) {
                additionalServiceSection.style.display = 'none';
            }
            if (twoSlotsSection) {
                twoSlotsSection.style.display = 'none';
            }

            // Показываем нужную секцию в зависимости от выбора
            if (this.value === 'additional' && additionalServiceSection) {
                additionalServiceSection.style.display = 'block';
                populateAdditionalServices();
                console.log('Showing additional service section');
            } else if (this.value === 'two_slots' && twoSlotsSection) {
                twoSlotsSection.style.display = 'block';
                console.log('Showing two slots section');
            }
        });
    });

    // Обновляем дополнительные услуги при изменении основной услуги
    if (serviceSelect && additionalServiceSelect) {
        serviceSelect.addEventListener('change', function() {
            if (additionalServiceSection.style.display === 'block') {
                populateAdditionalServices();
            }
        });
    }

    // Проверка существования пациента
    const checkPatientBtn = document.getElementById('checkPatientBtn');
    const patientCheckResult = document.getElementById('patientCheckResult');

    if (checkPatientBtn) {
        checkPatientBtn.addEventListener('click', function() {
            console.log('Check patient button clicked');

            const surname = document.getElementById('id_surname')?.value.trim();
            const firstName = document.getElementById('id_first_name')?.value.trim();
            const dateOfBirth = document.getElementById('id_date_of_birth')?.value;

            if (!patientCheckResult) {
                console.error('Patient check result element not found');
                return;
            }

            // Проверка обязательных полей
            if (!surname || !firstName) {
                patientCheckResult.innerHTML = '<div class="alert alert-warning">Заполните фамилию и имя для проверки</div>';
                patientCheckResult.style.display = 'block';
                return;
            }

            // Показываем загрузку
            patientCheckResult.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> Проверяем пациента в базе данных...</div>';
            patientCheckResult.style.display = 'block';

            // Создаем данные для отправки
            const requestData = {
                surname: surname,
                first_name: firstName
            };

            // Добавляем дату рождения если указана
            if (dateOfBirth) {
                requestData.date_of_birth = dateOfBirth;
            }

            console.log('Sending request with data:', requestData);

            // AJAX запрос для проверки пациента
            fetch(checkPatientUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(requestData)
            })
            .then(response => {
                console.log('Response status:', response.status);
                if (!response.ok) {
                    throw new Error('Ошибка сети: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                console.log('Received data:', data);
                if (data.error) {
                    patientCheckResult.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                    return;
                }

                if (data.exists) {
                    // Пациент найден
                    const patient = data.patient;
                    let message = `<div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle"></i>
                        <strong>Пациент уже существует в базе!</strong><br>`;

                    message += `<strong>ФИО:</strong> ${patient.full_name}<br>`;

                    if (patient.card_number) {
                        message += `<strong>Номер карты:</strong> ${patient.card_number}<br>`;
                    } else {
                        message += `<strong>Номер карты:</strong> не указан<br>`;
                    }

                    if (patient.phone_number) {
                        message += `<strong>Телефон:</strong> ${patient.phone_number}<br>`;
                    }

                    message += `<small class="text-muted">Система автоматически использует существующую запись при сохранении</small>`;
                    message += `</div>`;

                    patientCheckResult.innerHTML = message;
                } else {
                    // Пациент не найден
                    patientCheckResult.innerHTML = `<div class="alert alert-success">
                        <i class="fas fa-check-circle"></i>
                        <strong>Пациент не найден в базе.</strong><br>
                        Будет создана новая запись пациента.
                    </div>`;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                patientCheckResult.innerHTML = '<div class="alert alert-danger">Ошибка при проверке пациента: ' + error.message + '</div>';
            });
        });
    } else {
        console.error('Check patient button not found');
    }

    // Инициализация - убедимся, что при загрузке страницы правильные секции видны
    const checkedRadio = document.querySelector('input[name="appointment_type"]:checked');
    if (checkedRadio) {
        checkedRadio.dispatchEvent(new Event('change'));
    }

    console.log('Procedural appointment event listeners initialized successfully');
});