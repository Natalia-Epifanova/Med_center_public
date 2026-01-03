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

// Поиск пациента (асинхронная версия)
async function searchPatient() {
    const checkPatientBtn = document.getElementById('checkPatientBtn');
    const patientCheckResult = document.getElementById('patientCheckResult');

    if (!checkPatientBtn || !patientCheckResult) {
        console.error('Elements for patient search not found');
        return;
    }

    const surname = document.getElementById('id_surname')?.value.trim();
    const firstName = document.getElementById('id_first_name')?.value.trim();
    const phoneNumber = document.getElementById('id_phone_number')?.value.trim();

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

                patientCheckResult.innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle"></i>
                        <strong>Пациент найден в базе!</strong>
                        ${data.patient.card_number ? `Карта №${data.patient.card_number}` : ''}
                    </div>
                `;
            } else {
                patientCheckResult.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle"></i>
                        <strong>Пациент не найден.</strong> Будет создана новая запись.
                    </div>
                `;
            }
        } else {
            patientCheckResult.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-times-circle"></i>
                    <strong>Ошибка:</strong> ${data.error || 'Неизвестная ошибка'}
                </div>
            `;
        }
    } catch (error) {
        console.error('Error:', error);
        patientCheckResult.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-times-circle"></i>
                <strong>Ошибка подключения к серверу.</strong>
            </div>
        `;
    } finally {
        checkPatientBtn.disabled = false;
        checkPatientBtn.innerHTML = '<i class="fas fa-search"></i> Проверить пациента в базе';
        patientCheckResult.style.display = 'block';
    }
}

// Инициализация BloodTestSelection
function initializeBloodTestSelection() {
    console.log('Initializing BloodTestSelection...');
    console.log('initialTestIds before initialization:', initialTestIds);
    console.log('Type of initialTestIds:', typeof initialTestIds);

    const bloodTestSection = document.getElementById('bloodTestSelectionSection');
    if (!bloodTestSection) {
        console.error('Blood test section not found!');
        return;
    }

    // Преобразуем initialTestIds если это JSON-строка
    let parsedTestIds = [];
    try {
        if (typeof initialTestIds === 'string' && initialTestIds.trim().startsWith('[')) {
            parsedTestIds = JSON.parse(initialTestIds);
            console.log('Parsed test IDs from JSON string:', parsedTestIds);
        } else if (Array.isArray(initialTestIds)) {
            parsedTestIds = initialTestIds;
            console.log('InitialTestIds is already array:', parsedTestIds);
        } else {
            console.log('InitialTestIds is empty or invalid, using empty array');
            parsedTestIds = [];
        }
    } catch (e) {
        console.error('Error parsing initialTestIds:', e);
        parsedTestIds = [];
    }

    console.log('Final test IDs to initialize with:', parsedTestIds);

    // Инициализируем с начальными данными
    window.bloodTestSelection = new BloodTestSelection({
        initialTests: parsedTestIds
    });

    const serviceSelect = document.getElementById('id_service');
    if (serviceSelect) {
        const toggleBloodTestSection = () => {
            const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
            const isBloodTest = selectedOption && selectedOption.text.toLowerCase().includes('забор крови');

            console.log('Service change:', selectedOption ? selectedOption.text : 'none', 'Is blood test?', isBloodTest);

            if (bloodTestSection) {
                bloodTestSection.style.display = isBloodTest ? 'block' : 'none';

                if (!isBloodTest) {
                    window.bloodTestSelection.selectedTests.clear();
                    window.bloodTestSelection.renderSelectedTests();
                    updateTotalSum(0); // Обнуляем сумму
                } else {
                    updateTotalSum(); // Пересчитываем сумму
                }
            }
        };

        serviceSelect.addEventListener('change', toggleBloodTestSection);
        toggleBloodTestSection(); // Инициализация состояния
    }
}

// Функция обновления суммы
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

// Инициализация формы
document.addEventListener('DOMContentLoaded', function() {
    console.log('=== DEBUG: Procedural Appointment Update Form Loaded ===');
    console.log('DOM loaded, initialTestIds:', initialTestIds);

    // 1. Форматирование номера телефона
    const phoneInput = document.getElementById('id_phone_number');
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

    // 3. Кнопка поиска пациента
    const checkPatientBtn = document.getElementById('checkPatientBtn');
    if (checkPatientBtn) {
        checkPatientBtn.addEventListener('click', searchPatient);
    }

    // 4. Инициализация выбора анализов крови
    initializeBloodTestSelection();

    // 5. Слушаем изменения в выбранных анализах
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