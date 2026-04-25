function initializeServiceSearch() {
    console.log('Initializing service search...');
    console.log('Cabinet number:', cabinetNumber);

    // Получаем все select элементы с услугами
    const serviceSelects = document.querySelectorAll('select[id$="service"]');

    console.log('Found service selects:', serviceSelects.length);

    if (serviceSelects.length === 0) {
        console.warn('No service select elements found');
        return;
    }

    serviceSelects.forEach((select, index) => {
        console.log(`Initializing select #${index} with ${select.options.length} options`);

        // Для всех кабинетов делаем базовый Select2
        $(select).select2({
            placeholder: "Начните вводить название услуги...",
            allowClear: false,
            width: '100%',
            language: {
                noResults: function() {
                    return "Услуги не найдены";
                },
                searching: function() {
                    return "Поиск...";
                }
            }
        });

        // Для кабинета №5 делаем дополнительные настройки
        if (cabinetNumber === 5) {
            console.log('Cabinet 5 detected, enabling enhanced search');
            $(select).select2('destroy'); // Удаляем старую инициализацию

            $(select).select2({
                placeholder: "Введите название услуги для поиска...",
                allowClear: false,
                width: '100%',
                minimumInputLength: 2,  // Минимум 2 символа для поиска
                language: {
                    noResults: function() {
                        return "Ничего не найдено. Попробуйте другой запрос";
                    },
                    searching: function() {
                        return "Идет поиск...";
                    },
                    inputTooShort: function(args) {
                        var remainingChars = args.minimum - args.input.length;
                        return "Введите еще " + remainingChars + " символ" + (remainingChars === 1 ? "" : "а");
                    }
                }
            });
        }

        // ВАЖНО: Добавляем обработчик изменения для Select2
        $(select).on('select2:select', function(e) {
            console.log('Select2 changed:', e.params.data);

            // Симулируем стандартное событие change
            const event = new Event('change', { bubbles: true });
            select.dispatchEvent(event);

            // Дополнительно вызываем проверку для процедурного кабинета
            if (window.AppointmentUtils && window.AppointmentUtils.ProceduralManager) {
                const needsProceduralCheckbox = document.getElementById('id_needs_procedural');
                if (needsProceduralCheckbox) {
                    window.AppointmentUtils.ProceduralManager.updateProceduralCheckbox(
                        select,
                        needsProceduralCheckbox
                    );
                }
            }
        });
    });

    // Также инициализируем для дополнительных услуг, если они есть
    const additionalServiceSelect = document.getElementById('id_additional_service');
    if (additionalServiceSelect) {
        console.log('Found additional service select');
        $(additionalServiceSelect).select2({
            placeholder: "Начните вводить название услуги...",
            allowClear: false,
            width: '100%'
        });

        // Добавляем обработчик для дополнительной услуги
        $(additionalServiceSelect).on('select2:select', function(e) {
            console.log('Additional Select2 changed:', e.params.data);

            // Симулируем стандартное событие change
            const event = new Event('change', { bubbles: true });
            additionalServiceSelect.dispatchEvent(event);
        });
    }
}

function getDoctorName() {
    // Пробуем разные способы
    if (typeof doctorName !== 'undefined' && doctorName) {
        console.log('Got doctorName from template variable:', doctorName);
        return doctorName;
    }

    // Из заголовка
    const header = document.querySelector('.card-title');
    if (header) {
        const text = header.textContent.trim();
        console.log('Got doctorName from header:', text);
        return text;
    }

    // Из информационного блока
    const infoBlock = document.querySelector('.alert-info');
    if (infoBlock) {
        const text = infoBlock.textContent;
        const doctorMatch = text.match(/Врач:\s*([^\n]+)/);
        if (doctorMatch && doctorMatch[1]) {
            console.log('Got doctorName from info block:', doctorMatch[1].trim());
            return doctorMatch[1].trim();
        }
    }

    console.error('Could not determine doctor name');
    return '';
}

function initializePishchelevValidationForMainService() {
    console.log('=== Initializing Pishchelev validation ===');

    if (!window.AppointmentUtils || !window.AppointmentUtils.PishchelevValidator) {
        console.error('PishchelevValidator not found');
        return;
    }

    const mainServiceSelect = document.getElementById('id_service');
    if (!mainServiceSelect) {
        console.error('Main service select not found');
        return;
    }

    // Используем новую функцию для получения имени врача
    const doctorName = getDoctorName();

    if (!doctorName) {
        console.warn('Не удалось определить имя врача для валидации Пищелева');
        return;
    }

    console.log('Pishchelev validation initialized for doctor:', doctorName);

    // Инициализируем валидатор для основной услуги
    window.AppointmentUtils.PishchelevValidator.initializeForForm('id_service', doctorName);

    // Также проверяем сразу при загрузке, если услуга уже выбрана
    if (mainServiceSelect.value) {
        setTimeout(() => {
            window.AppointmentUtils.PishchelevValidator.validateServiceForPishchelev(
                mainServiceSelect, doctorName
            );
        }, 100);
    }
}

function initializeProceduralManagerForAdditionalService() {
    if (!window.AppointmentUtils || !window.AppointmentUtils.ProceduralManager) return;

    const additionalServiceSelect = document.getElementById('id_additional_service');
    const additionalProceduralVisibleCheckbox = document.getElementById('needs_procedural_additional_checkbox');
    const additionalProceduralSection = document.getElementById('additionalServiceProceduralSection');
    const additionalProceduralHiddenField = document.getElementById('id_needs_procedural_additional');

    if (additionalServiceSelect && additionalProceduralVisibleCheckbox && additionalProceduralSection) {
        additionalServiceSelect.addEventListener('change', function() {
            window.AppointmentUtils.ProceduralManager.updateProceduralCheckbox(
                this,
                additionalProceduralVisibleCheckbox
            );

            if (this.value) {
                additionalProceduralSection.style.display = 'block';
                const selectedOption = this.options[this.selectedIndex];
                const serviceName = selectedOption.text.toLowerCase();

                const needsProcedural = serviceName.includes('блокада') ||
                                       serviceName.includes('укол') ||
                                       serviceName.includes('пункция') ||
                                       serviceName.includes('введение') ||
                                       serviceName.includes('инъекция') ||
                                       serviceName.includes('внутримышечно') ||
                                       serviceName.includes('внутрикожно') ||
                                       serviceName.includes('внутривенно');

                if (needsProcedural) {
                    if (!additionalProceduralVisibleCheckbox.checked) {
                        additionalProceduralVisibleCheckbox.checked = true;
                    }
                    if (additionalProceduralHiddenField) {
                        additionalProceduralHiddenField.value = 'true';
                    }
                } else {
                    if (additionalProceduralVisibleCheckbox.checked) {
                        additionalProceduralVisibleCheckbox.checked = false;
                    }
                    if (additionalProceduralHiddenField) {
                        additionalProceduralHiddenField.value = 'false';
                    }
                }
            } else {
                additionalProceduralSection.style.display = 'none';
                if (additionalProceduralVisibleCheckbox.checked) {
                    additionalProceduralVisibleCheckbox.checked = false;
                }
                if (additionalProceduralHiddenField) {
                    additionalProceduralHiddenField.value = 'false';
                }
            }
        });

        if (additionalServiceSelect.value) {
            window.AppointmentUtils.ProceduralManager.updateProceduralCheckbox(
                additionalServiceSelect,
                additionalProceduralVisibleCheckbox
            );
            additionalProceduralSection.style.display = 'block';

            if (additionalProceduralHiddenField && additionalProceduralVisibleCheckbox.checked) {
                additionalProceduralHiddenField.value = 'true';
            }
        }
    }
}

function validatePishchelevBeforeSubmit() {
    const mainServiceSelect = document.getElementById('id_service');
    if (!mainServiceSelect) return true;

    // Получаем имя врача
    const doctorName = getDoctorName();
    if (!doctorName) return true;

    // Получаем выбранную услугу
    const selectedOption = mainServiceSelect.options[mainServiceSelect.selectedIndex];
    if (!selectedOption || !selectedOption.value) return true;

    const serviceName = selectedOption.textContent;

    // Получаем время из страницы
    const timeText = document.querySelector('.alert-info')?.textContent || '';
    const timeTextFromHidden = document.getElementById('js-original-time')?.value || '';
    const actualTimeText = timeText || timeTextFromHidden;

    // Проверяем через валидатор
    if (window.AppointmentUtils && window.AppointmentUtils.PishchelevValidator) {
        const slotDuration = window.AppointmentUtils.PishchelevValidator.getSlotDuration(actualTimeText);

        if (slotDuration !== null) {
            const validation = window.AppointmentUtils.PishchelevValidator.validateSlotForPishchelev(
                slotDuration, serviceName, doctorName
            );

            if (!validation.valid) {
                // Показываем ошибку и блокируем отправку
                alert('❌ Ошибка!\n\n' + validation.message +
                      '\n\nИсправьте выбор услуги или времени перед сохранением.');
                return false;
            }
        }
    }

    return true;
}

function initializeXRayWarning() {
    const serviceSelect = document.getElementById('id_service');

    if (!serviceSelect) return;

    // Список рентгеновских услуг
    const xrayServices = [
        'Рентгенография грудного отдела позвоночника (в 1ой проекции)',
        'Рентгенография грудного отдела позвоночника (в 2х проекциях)',
        'Рентгенография поясничного отдела позвоночника (в 1ой проекции)',
        'Рентгенография поясничного отдела позвоночника (в 2х проекциях)',
        'Рентгенография позвоночника с функциональными пробами (грудной отдел)',
        'Рентгенография позвоночника с функциональными пробами (поясничный отдел)'
    ];

    // Создаем блок для уведомления, если его нет
    let xrayWarningDiv = document.getElementById('xray-warning');
    if (!xrayWarningDiv) {
        xrayWarningDiv = document.createElement('div');
        xrayWarningDiv.id = 'xray-warning';
        xrayWarningDiv.className = 'alert alert-warning mt-3';
        xrayWarningDiv.style.display = 'none';
        xrayWarningDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            <strong>ВНИМАНИЕ! Рентгенография:</strong><br>
            СПРОСИТЬ ВЕС и РОСТ!<br>
            150-50 кг<br>
            160-60 кг<br>
            170-70 кг<br>
            180/190-80 кг<br>
            Больше 80кг нельзя!<br>
            Вес не больше роста - 100
        `;

        // Вставляем после блока с выбором услуги
        const serviceFormGroup = serviceSelect.closest('.mb-3');
        if (serviceFormGroup) {
            serviceFormGroup.parentNode.insertBefore(xrayWarningDiv, serviceFormGroup.nextSibling);
        }
    }

    // Функция проверки выбранной услуги
    function checkXRayService() {
        const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
        if (!selectedOption || !selectedOption.value) {
            xrayWarningDiv.style.display = 'none';
            return;
        }

        const serviceName = selectedOption.text.trim();

        // Проверяем, является ли услуга рентгеновской
        const isXRay = xrayServices.some(xray =>
            serviceName.toLowerCase().includes(xray.toLowerCase()) ||
            xray.toLowerCase().includes(serviceName.toLowerCase())
        );

        if (isXRay) {
            xrayWarningDiv.style.display = 'block';
        } else {
            xrayWarningDiv.style.display = 'none';
        }
    }

    // Добавляем обработчик события
    serviceSelect.addEventListener('change', checkXRayService);

    // Также отслеживаем выбор через Select2
    $(serviceSelect).on('select2:select', function(e) {
        setTimeout(checkXRayService, 100);
    });

    // Проверяем при загрузке, если услуга уже выбрана
    setTimeout(checkXRayService, 500);
}
