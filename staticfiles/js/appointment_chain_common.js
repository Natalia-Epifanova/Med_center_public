/**
 * Общие функции для работы с цепочками записей
 */

class AppointmentChainCommon {
    /**
     * Инициализация цепочек для формы
     * @param {Object} options - Опции инициализации
     */
    static initializeChainManager(options) {
        if (!window.AppointmentChainManager) {
            console.error('AppointmentChainManager не загружен');
            return null;
        }

        const requiredOptions = ['csrfToken', 'mainDoctorId', 'mainDate'];
        for (const option of requiredOptions) {
            if (!options[option]) {
                console.error(`Отсутствует обязательный параметр: ${option}`);
                return null;
            }
        }

        const chainManager = new AppointmentChainManager({
            csrfToken: options.csrfToken,
            mainDoctorId: options.mainDoctorId,
            mainDate: options.mainDate,
            maxAdditionalAppointments: options.maxAdditionalAppointments || 5,
            isProcedural: options.isProcedural || false
        });

        // Настройка обработчиков
        this.setupChainEventHandlers(chainManager, options);

        return chainManager;
    }

    /**
     * Настройка обработчиков событий для цепочек
     */
    static setupChainEventHandlers(chainManager, options) {
        // Кнопка добавления записи к врачу
        const addBtn = document.getElementById('addAppointmentForm');
        if (addBtn) {
            addBtn.addEventListener('click', () => chainManager.addAppointmentForm());
        }

        // Кнопка добавления еще одной записи
        const addAnotherBtn = document.getElementById('addAnotherAppointment');
        if (addAnotherBtn) {
            addAnotherBtn.addEventListener('click', () => chainManager.addAnotherDoctorForm());
        }

        // Обработчик отправки формы
        const appointmentForm = document.getElementById('appointmentForm');
        if (appointmentForm) {
            appointmentForm.addEventListener('submit', function(e) {
                if (!chainManager.validateBeforeSubmit()) {
                    e.preventDefault();
                    return false;
                }

                chainManager.updateHiddenField();
                chainManager.updateProceduralHiddenField();

                const chainType = document.querySelector('input[name="appointment_chain_type"]:checked');
                if (chainType) {
                    const value = chainType.value;
                    if ((value === 'another_doctor' || value === 'multiple') &&
                        chainManager.additionalAppointments.length === 0) {
                        alert('Пожалуйста, заполните данные дополнительной записи');
                        e.preventDefault();
                        return false;
                    }
                }
            });
        }
    }

    /**
     * Инициализация менеджера типа записи
     */
    static initializeAppointmentTypeManager() {
        const radios = document.querySelectorAll('input[name="appointment_chain_type"]');
        if (radios.length === 0) return;

        const sections = {
            sameDoctorSections: document.getElementById('sameDoctorSections'),
            additionalServiceSection: document.getElementById('additionalServiceSection'),
            twoSlotsSection: document.getElementById('twoSlotsSection'),
            anotherDoctorSection: document.getElementById('anotherDoctorSection'),
            multipleAppointmentsSection: document.getElementById('multipleAppointmentsSection')
        };

        const additionalServiceSelect = document.getElementById('id_additional_service');
        const mainServiceSelect = document.getElementById('id_service');

        function updateSectionsVisibility(value) {
            // Скрываем все секции
            Object.values(sections).forEach(section => {
                if (section) section.style.display = 'none';
            });

            // Показываем нужные секции
            switch(value) {
                case 'additional':
                    if (sections.sameDoctorSections) sections.sameDoctorSections.style.display = 'block';
                    if (sections.additionalServiceSection) sections.additionalServiceSection.style.display = 'block';
                    break;

                case 'two_slots':
                    if (sections.sameDoctorSections) sections.sameDoctorSections.style.display = 'block';
                    if (sections.twoSlotsSection) sections.twoSlotsSection.style.display = 'block';
                    break;

                case 'another_doctor':
                    if (sections.anotherDoctorSection) sections.anotherDoctorSection.style.display = 'block';
                    break;

                case 'multiple':
                    if (sections.multipleAppointmentsSection) sections.multipleAppointmentsSection.style.display = 'block';
                    break;
            }
        }

        function handleAppointmentTypeChange(event) {
            updateSectionsVisibility(event.target.value);
        }

        // Добавляем обработчики
        radios.forEach(radio => {
            radio.addEventListener('change', handleAppointmentTypeChange);
        });

        // Устанавливаем начальное состояние
        const checkedRadio = document.querySelector('input[name="appointment_chain_type"]:checked');
        if (checkedRadio) {
            updateSectionsVisibility(checkedRadio.value);
        }
    }
}

// Экспорт для использования
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AppointmentChainCommon;
}