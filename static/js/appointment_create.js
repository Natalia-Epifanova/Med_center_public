
// Функция для форматирования номера телефона
function formatPhoneNumber(input) {
    // Удаляем все нецифровые символы кроме +
    let value = input.value.replace(/[^\d+]/g, '');

    // Если номер начинается не с +7, форматируем его
    if (!value.startsWith('+7') && value.length > 0) {
        // Если начинается с 7 или 8, заменяем на +7
        if (value.startsWith('7') || value.startsWith('8')) {
            value = '+7' + value.slice(1);
        } else {
            // Иначе добавляем +7
            value = '+7' + value;
        }
    }

    // Ограничиваем длину до 12 символов
    if (value.length > 12) {
        value = value.substring(0, 12);
    }

    input.value = value;
}

document.addEventListener('DOMContentLoaded', function() {
    const appointmentTypeRadios = document.querySelectorAll('input[name="appointment_type"]');
    const additionalServiceSection = document.getElementById('additionalServiceSection');
    const twoSlotsSection = document.getElementById('twoSlotsSection');
    const additionalServiceSelect = document.getElementById('id_additional_service');

    console.log('DOM loaded - initializing event listeners');
    const phoneInput = document.getElementById('id_phone_number');

    if (phoneInput) {
        // Форматируем при вводе
        phoneInput.addEventListener('input', function() {
            formatPhoneNumber(this);
        });

        // Форматируем при потере фокуса
        phoneInput.addEventListener('blur', function() {
            formatPhoneNumber(this);
        });

        // Форматируем при загрузке страницы (если есть значение)
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
                console.log('Showing additional service section');
            } else if (this.value === 'two_slots' && twoSlotsSection) {
                twoSlotsSection.style.display = 'block';
                console.log('Showing two slots section');
            }
        });
    });

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

    console.log('Event listeners initialized successfully');
});
// Функция для проверки, является ли услуга медикаментозной блокадой
function isMedicalBlockade(serviceSelect) {
    const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
    const serviceName = selectedOption.text.toLowerCase();

    // Ключевые слова для идентификации блокад
    const blockadeKeywords = ['блокад', 'введение', 'инъекц', 'укол', 'инфузи'];

    return blockadeKeywords.some(keyword => serviceName.includes(keyword));
}

// Обработчик изменения выбора услуги
document.getElementById('id_service').addEventListener('change', function() {
    const needsProceduralCheckbox = document.getElementById('id_needs_procedural');

    if (needsProceduralCheckbox && isMedicalBlockade(this)) {
        // Автоматически отмечаем галочку для блокад
        needsProceduralCheckbox.checked = true;
    }
});

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    const serviceSelect = document.getElementById('id_service');
    const needsProceduralCheckbox = document.getElementById('id_needs_procedural');

    if (serviceSelect && needsProceduralCheckbox) {

        if (isMedicalBlockade(serviceSelect)) {
            needsProceduralCheckbox.checked = true;
        }
    }
});