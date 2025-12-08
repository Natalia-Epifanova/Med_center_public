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

// Функция для проверки, является ли услуга медикаментозной блокадой
function isMedicalBlockade(serviceSelect) {
    if (!serviceSelect) return false;

    const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
    if (!selectedOption || selectedOption.value === '') {
        return false;
    }

    const serviceName = selectedOption.text.toLowerCase();

    // Ключевые слова для идентификации блокад
    const blockadeKeywords = ['блокад', 'введение', 'инъекц', 'укол', 'инфузи'];

    return blockadeKeywords.some(keyword => serviceName.includes(keyword));
}

// Функция для проверки, является ли услуга изготовлением стелек
function isInsolesService(serviceName) {
    if (!serviceName) return false;

    const serviceNameLower = serviceName.toLowerCase();
    const insolesKeywords = ["стель", "стелек", "manufacture_of_insoles"];

    return insolesKeywords.some(keyword => serviceNameLower.includes(keyword));
}

// Функция для проверки ограничений врача Пищелева
function checkPishchelevRestrictions(doctorName, serviceName, slotDuration) {
    const isPishchelev = doctorName.includes('Пищелёв');
    const isInsolesServiceValue = isInsolesService(serviceName);

    console.log('Pishchelev restriction check:', {
        doctorName: doctorName,
        serviceName: serviceName,
        slotDuration: slotDuration,
        isPishchelev: isPishchelev,
        isInsolesService: isInsolesServiceValue
    });

    if (isPishchelev && slotDuration === 20 && !isInsolesServiceValue) {
        return {
            allowed: false,
            message: 'Врач Пищелев П.В. на 20-минутные интервалы принимает ТОЛЬКО на изготовление стелек. Выберите услугу "Изготовление стелек" или 30-минутный интервал.'
        };
    }

    return { allowed: true };
}

// Функция для расчета длительности слота из текста
function getSlotDurationFromText(timeText) {
    const timeMatch = timeText.match(/(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})/);
    if (timeMatch) {
        const startHours = parseInt(timeMatch[1]);
        const startMinutes = parseInt(timeMatch[2]);
        const endHours = parseInt(timeMatch[3]);
        const endMinutes = parseInt(timeMatch[4]);

        return (endHours * 60 + endMinutes) - (startHours * 60 + startMinutes);
    }
    return null;
}

// Функция для проверки ограничений при выборе услуги
function checkServiceRestrictions(serviceSelect) {
    if (!serviceSelect) return;

    const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
    if (!selectedOption) return;

    const serviceName = selectedOption.textContent;

    // Получаем информацию о враче и слоте
    const doctorName = document.querySelector('.card-title')?.textContent || '';
    const timeText = document.querySelector('.alert-info')?.textContent || '';

    console.log('Checking restrictions for:', {
        doctorName: doctorName,
        serviceName: serviceName,
        timeText: timeText
    });

    // Парсим длительность слота из времени
    const slotDuration = getSlotDurationFromText(timeText);
    if (slotDuration !== null) {
        console.log('Slot duration calculated:', slotDuration + ' minutes');

        // Проверяем ограничения
        const restriction = checkPishchelevRestrictions(doctorName, serviceName, slotDuration);
        if (!restriction.allowed) {
            alert(restriction.message);
            console.log('Restriction violated, but allowing selection');
        } else {
            console.log('No restrictions violated');
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DEBUG: Appointment Form Loaded ===');

    // ОСНОВНЫЕ ПЕРЕМЕННЫЕ
    const appointmentTypeRadios = document.querySelectorAll('input[name="appointment_type"]');
    const additionalServiceSection = document.getElementById('additionalServiceSection');
    const twoSlotsSection = document.getElementById('twoSlotsSection');
    const additionalServiceSelect = document.getElementById('id_additional_service');
    const serviceSelect = document.getElementById('id_service');
    const needsProceduralCheckbox = document.getElementById('id_needs_procedural');
    const phoneInput = document.getElementById('id_phone_number');
    const checkPatientBtn = document.getElementById('checkPatientBtn');
    const patientCheckResult = document.getElementById('patientCheckResult');

    console.log('Elements found:', {
        appointmentTypeRadios: appointmentTypeRadios.length,
        additionalServiceSection: !!additionalServiceSection,
        twoSlotsSection: !!twoSlotsSection,
        additionalServiceSelect: !!additionalServiceSelect,
        serviceSelect: !!serviceSelect,
        needsProceduralCheckbox: !!needsProceduralCheckbox,
        phoneInput: !!phoneInput,
        checkPatientBtn: !!checkPatientBtn,
        patientCheckResult: !!patientCheckResult
    });

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

    // Автоматическая отметка процедурного кабинета для блокад
    if (serviceSelect && needsProceduralCheckbox) {
        serviceSelect.addEventListener('change', function() {
            console.log('Service changed, checking for medical blockade');
            if (isMedicalBlockade(this)) {
                needsProceduralCheckbox.checked = true;
                console.log('Auto-checked procedural for medical blockade');
            }
        });

        // Инициализация при загрузке
        if (isMedicalBlockade(serviceSelect)) {
            needsProceduralCheckbox.checked = true;
            console.log('Initial medical blockade detected');
        }
    }

    // Обработка изменения типа записи
    if (appointmentTypeRadios.length > 0) {
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
    } else {
        console.error('No appointment type radios found');
    }

    // Проверка ограничений врача Пищелева при выборе услуги
    if (serviceSelect) {
        serviceSelect.addEventListener('change', function() {
            checkServiceRestrictions(this);
        });

        // Также проверяем при загрузке страницы
        checkServiceRestrictions(serviceSelect);
    }

    // Проверка существования пациента
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
        console.log('Initial radio checked:', checkedRadio.value);
        checkedRadio.dispatchEvent(new Event('change'));
    } else {
        console.log('No radio checked by default');
    }

    console.log('Event listeners initialized successfully');
});