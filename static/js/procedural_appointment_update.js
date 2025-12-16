document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DEBUG: Procedural Appointment Update Form Loaded ===');
    console.log('DOM loaded, initialTestIds:', initialTestIds);

    // Проверяем, что утилиты загружены
    if (!window.AppointmentUtils) {
        console.error('AppointmentUtils не загружен');
        return;
    }

    // 1. Форматирование номера телефона
    const phoneInput = document.getElementById('id_phone_number');
    if (phoneInput) {
        window.AppointmentUtils.PhoneFormatter.initialize(phoneInput);
    }

    // 2. Создание скрытых полей если их нет
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

    // 3. Инициализация проверки пациента (используем старую функцию, т.к. она специфична)
    const checkPatientBtn = document.getElementById('checkPatientBtn');
    if (checkPatientBtn) {
        // Используем существующую функцию searchPatient
        checkPatientBtn.addEventListener('click', async function() {
            const surname = document.getElementById('id_surname')?.value.trim();
            const firstName = document.getElementById('id_first_name')?.value.trim();
            const phoneNumber = document.getElementById('id_phone_number')?.value.trim();
            const patientCheckResult = document.getElementById('patientCheckResult');

            if (!surname && !firstName && !phoneNumber) {
                alert('Пожалуйста, заполните хотя бы одно поле (Фамилия, Имя или Телефон) для поиска.');
                return;
            }

            try {
                checkPatientBtn.disabled = true;
                checkPatientBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Поиск...';

                const response = await fetch(checkPatientUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': csrfToken
                    },
                    body: new URLSearchParams({
                        'surname': surname,
                        'first_name': firstName,
                        'phone_number': phoneNumber
                    })
                });

                const data = await response.json();

                if (data.success) {
                    if (data.patient) {
                        // Заполняем поля формы данными пациента
                        document.getElementById('id_surname').value = data.patient.surname || '';
                        document.getElementById('id_first_name').value = data.patient.first_name || '';
                        document.getElementById('id_last_name').value = data.patient.last_name || '';
                        document.getElementById('id_phone_number').value = data.patient.phone_number || '';
                        document.getElementById('id_card_number').value = data.patient.card_number || '';

                        if (data.patient.date_of_birth) {
                            const dob = new Date(data.patient.date_of_birth);
                            const formattedDob = dob.toISOString().split('T')[0];
                            document.getElementById('id_date_of_birth').value = formattedDob;
                        }

                        if (patientCheckResult) {
                            patientCheckResult.innerHTML = `
                                <div class="alert alert-success">
                                    <i class="fas fa-check-circle"></i>
                                    <strong>Пациент найден в базе!</strong>
                                    ${data.patient.card_number ? `Карта №${data.patient.card_number}` : ''}
                                </div>
                            `;
                            patientCheckResult.style.display = 'block';
                        }
                    } else {
                        if (patientCheckResult) {
                            patientCheckResult.innerHTML = `
                                <div class="alert alert-warning">
                                    <i class="fas fa-exclamation-triangle"></i>
                                    <strong>Пациент не найден.</strong> Будет создана новая запись.
                                </div>
                            `;
                            patientCheckResult.style.display = 'block';
                        }
                    }
                } else {
                    if (patientCheckResult) {
                        patientCheckResult.innerHTML = `
                            <div class="alert alert-danger">
                                <i class="fas fa-times-circle"></i>
                                <strong>Ошибка:</strong> ${data.error || 'Неизвестная ошибка'}
                            </div>
                        `;
                        patientCheckResult.style.display = 'block';
                    }
                }
            } catch (error) {
                console.error('Error:', error);
                if (patientCheckResult) {
                    patientCheckResult.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-times-circle"></i>
                            <strong>Ошибка подключения к серверу.</strong>
                        </div>
                    `;
                    patientCheckResult.style.display = 'block';
                }
            } finally {
                checkPatientBtn.disabled = false;
                checkPatientBtn.innerHTML = '<i class="fas fa-search"></i> Проверить пациента в базе';
            }
        });
    }

    // 4. Инициализация выбора анализов крови
    if (typeof initializeBloodTestSelection === 'function') {
        initializeBloodTestSelection();
    }

    // 5. Функция обновления суммы
    function updateTotalSum(customSum = null) {
        const totalField = document.getElementById('id_total_sum');
        if (!totalField) {
            console.error('Total sum field not found!');
            return;
        }

        if (customSum !== null) {
            totalField.value = customSum.toFixed(2);
        } else {
            // Считаем сумму анализов + услугу
            let total = 0;

            // Сумма анализов
            if (window.bloodTestSelection && window.bloodTestSelection.selectedTests) {
                window.bloodTestSelection.selectedTests.forEach(testId => {
                    const test = window.bloodTestSelection.allTests.find(t => t.id === testId);
                    if (test && test.price) {
                        total += test.price;
                    }
                });
            }

            // Добавляем стоимость услуги
            const serviceSelect = document.getElementById('id_service');
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

    // 6. Обработчик отправки формы
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

    console.log('Procedural appointment update form initialized successfully');
});