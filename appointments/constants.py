# appointments/constants.py

# Константы для записей на прием
PROCEDURAL_CABINET_NUMBER = 6  # Номер процедурного кабинета
SLOT_LOCK_TIMEOUT = 300  # 10 минут в секундах

# Ключи кэша
CACHE_KEYS = {
    "DOCTOR_SERVICES": "doctor_services_{doctor_id}",
    "BLOOD_TESTS": "blood_tests_tree",
    "ACTIVE_DOCTORS": "active_doctors_list",
    "DOCTOR_SLOTS": "doctor_slots_{doctor_id}_{date}",
    "SLOT_LOCK": "slot_lock_{slot_id}",
    "PROCEDURAL_CABINET": "procedural_cabinet_object",  # Кэш для объекта кабинета
    "DOCTOR_SERVICES_DETAILED": "doctor_services_detailed_{doctor_id}",
    "DOCTOR_SLOTS_DETAILED": "doctor_slots_detailed_{doctor_id}_{date}",
}

# Типы цепочек записей
APPOINTMENT_CHAIN_CHOICES = [
    ("none", "Только одна услуга"),
    ("two_slots", "Запись на два последовательных слота (ДЛЯ КОНС К О.Е.!!!)"),
    ("another_doctor", "Добавить запись к этому или другому врачу"),
    ("multiple", "Несколько записей к разным врачам"),
]

# Длительность кэширования (в секундах)
CACHE_TIMEOUTS = {
    "DOCTOR_SERVICES": 3600,  # 1 час
    "BLOOD_TESTS": 7200,  # 2 часа
    "ACTIVE_DOCTORS": 1800,  # 30 минут
    "DOCTOR_SLOTS": 300,  # 5 минут
    "PROCEDURAL_CABINET": 86400,  # 24 часа (редко меняется)
    "DOCTOR_SLOTS_DETAILED": 180,  # 3 минуты для детализированных данных
}
