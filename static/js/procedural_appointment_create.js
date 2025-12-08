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
    console.log('Initial test IDs:', initialTestIds); // Используем глобальную переменную

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

    // Убеждаемся, что поля существуют
    const testsField = document.getElementById('id_selected_blood_tests');
    const totalField = document.getElementById('id_total_sum');

    if (!testsField) {
        const form = document.getElementById('appointmentForm');
        if (form) {
            const hiddenField = document.createElement('input');
            hiddenField.type = 'hidden';
            hiddenField.id = 'id_selected_blood_tests';
            hiddenField.name = 'selected_blood_tests_input';
            form.appendChild(hiddenField);
        }
    }

    if (!totalField) {
        const form = document.getElementById('appointmentForm');
        if (form) {
            const hiddenField = document.createElement('input');
            hiddenField.type = 'hidden';
            hiddenField.id = 'id_total_sum';
            hiddenField.name = 'total_sum';
            form.appendChild(hiddenField);
        }
    }

    // ========== КОД ДЛЯ ПОИСКА ПАЦИЕНТА ==========
    const checkPatientBtn = document.getElementById('checkPatientBtn');
    const patientCheckResult = document.getElementById('patientCheckResult');

    if (checkPatientBtn && patientCheckResult) {
        checkPatientBtn.addEventListener('click', function() {
            console.log('Check patient button clicked (procedural)');

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

            // AJAX запрос для проверки пациента - отправляем как JSON
            fetch(checkPatientUrl, {  // Используем глобальную переменную
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken  // Используем глобальную переменную
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

                    // Автоматически заполняем поля формы
                    document.getElementById('id_surname').value = patient.surname || '';
                    document.getElementById('id_first_name').value = patient.first_name || '';
                    document.getElementById('id_last_name').value = patient.last_name || '';
                    document.getElementById('id_phone_number').value = patient.phone_number || '';
                    document.getElementById('id_card_number').value = patient.card_number || '';

                    if (patient.date_of_birth) {
                        const dob = new Date(patient.date_of_birth);
                        const formattedDob = dob.toISOString().split('T')[0];
                        document.getElementById('id_date_of_birth').value = formattedDob;
                    }
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
            })
            .finally(() => {
                patientCheckResult.style.display = 'block';
            });
        });
    } else {
        console.error('Check patient elements not found in procedural form');
    }
    // ========== КОНЕЦ КОДА ДЛЯ ПОИСКА ПАЦИЕНТА ==========

    // Инициализация BloodTestSelection
    const bloodTestSection = document.getElementById('bloodTestSelectionSection');
    if (bloodTestSection) {
        console.log('Initializing BloodTestSelection with tests:', initialTestIds);

        // Инициализируем с начальными данными
        window.bloodTestSelection = new BloodTestSelection({
            initialTests: initialTestIds
        });

        if (serviceSelect) {
            const toggleBloodTestSection = () => {
                const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
                const isBloodTest = selectedOption && selectedOption.text.toLowerCase().includes('забор крови');

                console.log('Service change:', selectedOption ? selectedOption.text : 'none', 'Is blood test?', isBloodTest);

                if (bloodTestSection) {
                    bloodTestSection.style.display = isBloodTest ? 'block' : 'none';

                    if (!isBloodTest) {
                        if (window.bloodTestSelection) {
                            window.bloodTestSelection.selectedTests.clear();
                            window.bloodTestSelection.renderSelectedTests();
                            updateTotalSum(0); // Обнуляем сумму
                        }
                    } else {
                        updateTotalSum(); // Пересчитываем сумму
                    }
                }
            };

            serviceSelect.addEventListener('change', toggleBloodTestSection);
            toggleBloodTestSection(); // Инициализация состояния
        }

        // Функция обновления суммы
        function updateTotalSum(customSum = null) {
            const totalField = document.getElementById('id_total_sum');
            if (!totalField) return;

            if (customSum !== null) {
                totalField.value = customSum.toFixed(2);
            } else {
                // Считаем сумму анализов + услугу
                let total = 0;

                // Сумма анализов
                if (window.bloodTestSelection) {
                    window.bloodTestSelection.selectedTests.forEach(testId => {
                        const test = window.bloodTestSelection.allTests.find(t => t.id === testId);
                        if (test && test.price) {
                            total += test.price;
                        }
                    });
                }

                // Добавляем стоимость услуги
                if (serviceSelect && serviceSelect.value) {
                    const servicePrice = 150; // Цена забора крови
                    total += servicePrice;
                }

                totalField.value = total.toFixed(2);
            }

            console.log('Total sum updated:', totalField.value);
        }

        // Слушаем изменения в выбранных анализах
        document.addEventListener('bloodTestsUpdated', function() {
            updateTotalSum();
        });

        // Обработчик отправки формы
        const appointmentForm = document.getElementById('appointmentForm');
        if (appointmentForm) {
            appointmentForm.addEventListener('submit', function(e) {
                // Обновляем оба скрытых поля перед отправкой
                if (window.bloodTestSelection) {
                    window.bloodTestSelection.updateFormField();
                    updateTotalSum(); // Убедимся, что сумма обновлена

                    console.log('Form submit - tests:', document.getElementById('id_selected_blood_tests').value);
                    console.log('Form submit - total:', document.getElementById('id_total_sum').value);
                }
            });
        }
    }

    // Инициализация - убедимся, что при загрузке страницы правильные секции видны
    const checkedRadio = document.querySelector('input[name="appointment_type"]:checked');
    if (checkedRadio) {
        checkedRadio.dispatchEvent(new Event('change'));
    }

    console.log('Procedural appointment event listeners initialized successfully');
});