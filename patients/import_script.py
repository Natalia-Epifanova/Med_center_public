import pandas as pd
import os
import sys
from datetime import datetime
from django.core.exceptions import ValidationError

# Настройка Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.append("C:/Users/user/PycharmProjects/Revmamed")

import django

django.setup()

from patients.models import Patient
from django.db import transaction, IntegrityError


def parse_date(date_value):
    """Преобразование даты из Excel формата"""
    if pd.isna(date_value):
        return None

    # Если это pandas Timestamp (дата из Excel)
    if isinstance(date_value, pd.Timestamp):
        try:
            return date_value.date()
        except:
            return None

    # Если это datetime
    if isinstance(date_value, datetime):
        return date_value.date()

    # Если это строка в формате дд.мм.гггг
    if isinstance(date_value, str):
        try:
            return datetime.strptime(date_value.strip(), "%d.%m.%Y").date()
        except:
            return None

    return None


def map_gender(gender_str):
    """Преобразование пола из русского в системный формат"""
    if pd.isna(gender_str):
        return ""

    gender = str(gender_str).strip().lower()
    if gender in ["мужской", "муж", "м", "male"]:
        return "male"
    elif gender in ["женский", "жен", "ж", "female"]:
        return "female"
    else:
        return ""


def clean_phone(phone):
    """Очистка номера телефона от лишних символов"""
    if pd.isna(phone) or phone is None:
        return None

    # Преобразуем в строку
    phone_str = str(phone).strip()

    # Если строка пустая или содержит только пробелы
    if not phone_str:
        return None

    # Удаляем все пробелы, скобки, тире и другие нецифровые символы кроме +
    cleaned = "".join(c for c in phone_str if c.isdigit() or c == "+")

    # Если после очистки ничего не осталось
    if not cleaned:
        return None

    # Проверяем и корректируем формат
    if cleaned.startswith("+7") and len(cleaned) == 12:
        return cleaned
    elif cleaned.startswith("7") and len(cleaned) == 11:
        return "+" + cleaned
    elif cleaned.startswith("8") and len(cleaned) == 11:
        return "+7" + cleaned[1:]
    elif len(cleaned) == 10:
        return "+7" + cleaned
    elif len(cleaned) > 12:
        # Если слишком длинный, берем первые 12 символов
        return cleaned[:12]
    else:
        # Если формат не распознан, все равно возвращаем очищенный номер
        return cleaned


def update_patient(patient, row, card_number_int):
    """Обновление данных пациента, если они отсутствуют"""
    updated = False
    changes = []  # Список изменений для отладки

    # Номер карты (самое важное!)
    if not patient.card_number and card_number_int:
        patient.card_number = card_number_int
        updated = True
        changes.append(f"добавлен номер карты: {card_number_int}")

    # Дата рождения
    if not patient.date_of_birth:
        date_of_birth = parse_date(row.get("Дата рождения"))
        if date_of_birth:
            patient.date_of_birth = date_of_birth
            updated = True
            changes.append(f"добавлена дата рождения: {date_of_birth}")

    # Пол
    if not patient.gender:
        gender = map_gender(row.get("ПОЛ"))
        if gender:
            patient.gender = gender
            updated = True
            changes.append(f"добавлен пол: {gender}")

    # Телефон - ВАЖНО: проверяем не только если пустое, но и формат
    phone_from_excel = clean_phone(row.get("телефон"))
    if phone_from_excel:
        # Если в базе нет телефона ИЛИ телефон в базе отличается от Excel
        if not patient.phone_number:
            patient.phone_number = phone_from_excel
            updated = True
            changes.append(f"добавлен телефон: {phone_from_excel}")
        elif patient.phone_number != phone_from_excel:
            # Проверяем, не просто ли разный формат (например, +79091234567 vs 89091234567)
            # Приводим к общему формату для сравнения
            db_phone_clean = "".join(
                c for c in patient.phone_number if c.isdigit() or c == "+"
            )
            excel_phone_clean = "".join(
                c for c in phone_from_excel if c.isdigit() or c == "+"
            )

            if db_phone_clean != excel_phone_clean:
                # Телефоны действительно разные
                changes.append(
                    f"телефон в базе отличается: {patient.phone_number} vs Excel: {phone_from_excel}"
                )
                # Не обновляем автоматически разные телефоны

    # Адресные данные - проверяем каждое поле отдельно
    address_fields = {
        "area": "Субьект",
        "locality": "город",
        "city": "город",
        "street": "улица",
        "home": "дом",
        "apartment": "квартира",
    }

    for field, excel_column in address_fields.items():
        if excel_column in row and not pd.isna(row[excel_column]):
            current_value = getattr(patient, field)
            new_value = str(row[excel_column]).strip()

            # Проверяем, нужно ли обновить поле
            if not current_value or str(current_value).strip() == "":
                if new_value and new_value.lower() != "nan":
                    setattr(patient, field, new_value)
                    updated = True
                    changes.append(f"добавлен {field}: {new_value}")

    return updated, changes


def import_patients_from_excel(file_path):
    """
    Импорт пациентов из Excel файла

    Args:
        file_path: Путь к Excel файлу
    """
    try:
        # Чтение Excel файла
        print(f"Чтение файла: {file_path}")

        # Читаем Excel с указанием типа данных для колонки телефона
        df = pd.read_excel(file_path, dtype={"телефон": str})
        df.columns = df.columns.str.strip()

        print(f"Загружено {len(df)} записей из файла")
        print(f"Колонки в файле: {list(df.columns)}")

        # Проверяем первые несколько строк для отладки
        print("\nПервые 5 строк данных для проверки:")
        for i in range(min(5, len(df))):
            row = df.iloc[i]
            print(
                f"Строка {i+2}: ФИО: {row.get('Фамилия', '')} {row.get('Имя', '')}, "
                f"Телефон: '{row.get('телефон', '')}', "
                f"Тип телефона: {type(row.get('телефон'))}"
            )

        # Проверяем наличие обязательных колонок
        required_columns = ["НОМЕР КАРТЫ", "Фамилия", "Имя"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            print(f"Ошибка: отсутствуют обязательные колонки: {missing_columns}")
            print(f"Доступные колонки: {list(df.columns)}")
            return

        # Статистика и списки для отчетов
        stats = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "manual_check": 0,
        }

        manual_check_patients = []  # Пациенты для ручной проверки

        # Загружаем существующих пациентов
        print("\nЗагрузка существующих пациентов для быстрого поиска...")
        existing_patients = Patient.objects.all()
        existing_names_cache = {}

        for p in existing_patients:
            # Ключ для поиска: фамилия + имя + отчество (нижний регистр)
            if p.last_name:
                key_full = (
                    f"{p.surname.lower()} {p.first_name.lower()} {p.last_name.lower()}"
                )
                existing_names_cache[key_full] = p
            # Также добавляем ключ без отчества
            key_short = f"{p.surname.lower()} {p.first_name.lower()}"
            existing_names_cache[key_short] = p

        # Используем транзакцию для безопасности
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    # Пропускаем полностью пустые строки
                    if row.isnull().all():
                        continue

                    card_number = row["НОМЕР КАРТЫ"]

                    # Пропускаем пустые номера карт
                    if pd.isna(card_number):
                        print(f"Строка {index + 2}: пропущена - нет номера карты")
                        stats["skipped"] += 1
                        continue

                    # Преобразуем номер карты в число
                    try:
                        if isinstance(card_number, float):
                            card_number_int = int(card_number)
                        else:
                            card_number_int = int(
                                str(card_number).strip().split(".")[0]
                            )
                    except (ValueError, AttributeError) as e:
                        print(
                            f"Строка {index + 2}: некорректный номер карты '{card_number}' - {e}"
                        )
                        stats["errors"] += 1
                        continue

                    # Извлекаем ФИО из строки Excel
                    excel_surname = (
                        str(row["Фамилия"]).strip()
                        if not pd.isna(row["Фамилия"])
                        else ""
                    )
                    excel_first_name = (
                        str(row["Имя"]).strip() if not pd.isna(row["Имя"]) else ""
                    )
                    excel_last_name = (
                        str(row["Отчество"]).strip()
                        if not pd.isna(row.get("Отчество"))
                        else ""
                    )

                    if not excel_surname or not excel_first_name:
                        print(f"Строка {index + 2}: пропущена - нет фамилии или имени")
                        stats["errors"] += 1
                        continue

                    # Формируем ключи для поиска
                    key_full = (
                        f"{excel_surname.lower()} {excel_first_name.lower()} {excel_last_name.lower()}"
                        if excel_last_name
                        else None
                    )
                    key_short = f"{excel_surname.lower()} {excel_first_name.lower()}"

                    # Ищем существующего пациента
                    patient = None

                    # 1. Сначала ищем по номеру карты (самый надежный способ)
                    if card_number_int:
                        patient = Patient.objects.filter(
                            card_number=card_number_int
                        ).first()
                        if patient:
                            print(
                                f"Строка {index + 2}: найден по номеру карты {card_number_int}"
                            )

                    # 2. Если нашли по номеру карты - обновляем
                    if patient:
                        # Обновляем данные пациента
                        updated, changes = update_patient(patient, row, card_number_int)

                        if updated:
                            try:
                                patient.full_clean()
                                patient.save()

                                # Формируем сообщение об изменениях
                                changes_str = (
                                    ", ".join(changes)
                                    if changes
                                    else "данные обновлены"
                                )
                                print(
                                    f"Строка {index + 2}: ОБНОВЛЕН {patient.full_name} (карта: {card_number_int}) - {changes_str}"
                                )
                                stats["updated"] += 1
                            except ValidationError as e:
                                print(
                                    f"Строка {index + 2}: ошибка валидации при обновлении: {e}"
                                )
                                stats["errors"] += 1
                            except IntegrityError as e:
                                print(
                                    f"Строка {index + 2}: ошибка целостности при обновлении: {e}"
                                )
                                stats["errors"] += 1
                            except Exception as e:
                                print(f"Строка {index + 2}: ошибка обновления: {e}")
                                stats["errors"] += 1
                        else:
                            print(
                                f"Строка {index + 2}: пациент {patient.full_name} уже имеет все данные (пропущено)"
                            )
                            stats["skipped"] += 1

                        continue  # Переходим к следующей строке

                    # 3. Если не нашли по номеру карты, проверяем по ФИО
                    #    Но НЕ создаем нового и НЕ обновляем, если нашли по ФИО без номера карты
                    found_by_name = False
                    found_patient = None

                    # Сначала ищем по полному ФИО
                    if key_full and key_full in existing_names_cache:
                        found_patient = existing_names_cache[key_full]
                        found_by_name = True

                    # Если не нашли по полному, ищем по короткому (без отчества)
                    if not found_patient and key_short in existing_names_cache:
                        found_patient = existing_names_cache[key_short]
                        found_by_name = True

                    # Если нашли пациента по ФИО (без номера карты)
                    if found_patient and found_by_name:
                        print(
                            f"Строка {index + 2}: найден по ФИО: {found_patient.full_name}"
                        )

                        # Проверяем даты рождения для дополнительной проверки
                        excel_date_of_birth = parse_date(row.get("Дата рождения"))
                        db_date_of_birth = found_patient.date_of_birth

                        # Если даты рождения разные или обе пустые, это дополнительный признак того, что нужно проверить
                        dates_match = (excel_date_of_birth == db_date_of_birth) or (
                            not excel_date_of_birth and not db_date_of_birth
                        )

                        # Добавляем в список для ручной проверки
                        patient_info = {
                            "row": index + 2,
                            "excel_data": {
                                "card_number": card_number_int,
                                "full_name": f"{excel_surname} {excel_first_name} {excel_last_name}",
                                "date_of_birth": excel_date_of_birth,
                                "phone": clean_phone(row.get("телефон")),
                                "address": f"{row.get('город', '')}, {row.get('улица', '')} {row.get('дом', '')}",
                            },
                            "db_data": {
                                "id": found_patient.id,
                                "full_name": found_patient.full_name,
                                "card_number": found_patient.card_number,
                                "date_of_birth": db_date_of_birth,
                                "phone": found_patient.phone_number,
                                "address": found_patient.full_address,
                            },
                            "reason": "найден пациент с такими же ФИО, но без номера карты в базе",
                        }

                        if not dates_match:
                            patient_info["reason"] += " (даты рождения различаются)"

                        manual_check_patients.append(patient_info)

                        print(
                            f"Строка {index + 2}: ТРЕБУЕТ РУЧНОЙ ПРОВЕРКИ - найден пациент с такими же ФИО: {found_patient.full_name} (ID: {found_patient.id})"
                        )
                        stats["manual_check"] += 1
                        continue  # Не создаем нового пациента, пропускаем

                    # 4. Если не нашли ни по номеру карты, ни по ФИО - создаем нового пациента
                    patient = Patient()
                    patient.surname = excel_surname
                    patient.first_name = excel_first_name

                    if excel_last_name:
                        patient.last_name = excel_last_name

                    if card_number_int:
                        patient.card_number = card_number_int

                    # Дата рождения
                    date_of_birth = parse_date(row.get("Дата рождения"))
                    if date_of_birth:
                        patient.date_of_birth = date_of_birth

                    # Пол
                    gender = map_gender(row.get("ПОЛ"))
                    if gender:
                        patient.gender = gender

                    # Телефон - ВАЖНО: проверяем перед сохранением
                    phone = clean_phone(row.get("телефон"))
                    print(
                        f"Строка {index + 2}: исходный телефон: '{row.get('телефон')}', очищенный: '{phone}'"
                    )
                    if phone:
                        patient.phone_number = phone

                    # Адресные данные
                    address_mapping = [
                        ("area", "Субьект"),
                        ("locality", "город"),
                        ("city", "город"),
                        ("street", "улица"),
                        ("home", "дом"),
                        ("apartment", "квартира"),
                    ]

                    for field_name, excel_col in address_mapping:
                        if excel_col in row and not pd.isna(row[excel_col]):
                            value = str(row[excel_col]).strip()
                            if value and value.lower() != "nan":
                                setattr(patient, field_name, value)

                    try:
                        patient.full_clean()
                        patient.save()
                        print(
                            f"Строка {index + 2}: СОЗДАН новый пациент {patient.full_name} (карта: {card_number_int})"
                        )
                        if phone:
                            print(f"       Телефон добавлен: {phone}")
                        stats["created"] += 1

                        # Добавляем в кэш
                        new_key = (
                            f"{patient.surname.lower()} {patient.first_name.lower()}"
                        )
                        existing_names_cache[new_key] = patient
                        if patient.last_name:
                            new_key_full = f"{patient.surname.lower()} {patient.first_name.lower()} {patient.last_name.lower()}"
                            existing_names_cache[new_key_full] = patient

                    except ValidationError as e:
                        print(f"Строка {index + 2}: ошибка валидации при создании: {e}")
                        stats["errors"] += 1
                    except IntegrityError as e:
                        print(
                            f"Строка {index + 2}: ошибка целостности при создании: {e}"
                        )
                        stats["errors"] += 1
                    except Exception as e:
                        print(f"Строка {index + 2}: ошибка создания: {e}")
                        stats["errors"] += 1

                except Exception as e:
                    print(f"Строка {index + 2}: общая ошибка: {e}")
                    import traceback

                    traceback.print_exc()
                    stats["errors"] += 1

                # Вывод прогресса
                if (index + 1) % 100 == 0:
                    print(f"Обработано {index + 1} строк...")

        # Вывод статистики
        print("\n" + "=" * 50)
        print("СТАТИСТИКА ИМПОРТА:")
        print(f"Создано новых пациентов: {stats['created']}")
        print(f"Обновлено существующих: {stats['updated']}")
        print(f"Пропущено (без изменений): {stats['skipped']}")
        print(f"Требуют ручной проверки: {stats['manual_check']}")
        print(f"Ошибок: {stats['errors']}")
        print(f"Всего обработано строк: {len(df)}")
        print("=" * 50)

        # Общая статистика БД
        total_patients = Patient.objects.count()
        print(f"Всего пациентов в БД: {total_patients}")

        # Вывод списка пациентов для ручной проверки
        if manual_check_patients:
            print("\n" + "=" * 50)
            print("ПАЦИЕНТЫ ДЛЯ РУЧНОЙ ПРОВЕРКИ:")
            print("=" * 50)

            for i, patient_info in enumerate(manual_check_patients, 1):
                print(f"\n{i}. Строка Excel: {patient_info['row']}")
                print(f"   Данные из Excel:")
                print(f"     • ФИО: {patient_info['excel_data']['full_name']}")
                print(
                    f"     • Номер карты: {patient_info['excel_data']['card_number']}"
                )
                print(
                    f"     • Дата рождения: {patient_info['excel_data']['date_of_birth']}"
                )
                print(f"     • Телефон: {patient_info['excel_data']['phone']}")
                print(f"     • Адрес: {patient_info['excel_data']['address']}")

                print(
                    f"   Существующий пациент в базе (ID: {patient_info['db_data']['id']}):"
                )
                print(f"     • ФИО: {patient_info['db_data']['full_name']}")
                print(f"     • Номер карты: {patient_info['db_data']['card_number']}")
                print(
                    f"     • Дата рождения: {patient_info['db_data']['date_of_birth']}"
                )
                print(f"     • Телефон: {patient_info['db_data']['phone']}")
                print(f"     • Адрес: {patient_info['db_data']['address']}")

                print(f"   ПРИЧИНА: {patient_info['reason']}")
                print(
                    f"   ДЕЙСТВИЕ: Проверить, один ли это пациент. Если да - обновить номер карты и другие данные вручную."
                )

            print(
                f"\nВсего пациентов для ручной проверки: {len(manual_check_patients)}"
            )

            # Сохраняем отчет в файл
            try:
                report_file = f"manual_check_patients_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(report_file, "w", encoding="utf-8") as f:
                    f.write("ОТЧЕТ О ПАЦИЕНТАХ ДЛЯ РУЧНОЙ ПРОВЕРКИ\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(
                        "Найдены пациенты с одинаковыми ФИО, но без номера карты в базе.\n"
                    )
                    f.write(
                        "Требуется ручная проверка - возможно, это один и тот же пациент.\n\n"
                    )

                    for i, patient_info in enumerate(manual_check_patients, 1):
                        f.write(f"{i}. Строка Excel: {patient_info['row']}\n")
                        f.write(f"   Данные из Excel:\n")
                        f.write(
                            f"     • ФИО: {patient_info['excel_data']['full_name']}\n"
                        )
                        f.write(
                            f"     • Номер карты: {patient_info['excel_data']['card_number']}\n"
                        )
                        f.write(
                            f"     • Дата рождения: {patient_info['excel_data']['date_of_birth']}\n"
                        )
                        f.write(
                            f"     • Телефон: {patient_info['excel_data']['phone']}\n"
                        )
                        f.write(
                            f"     • Адрес: {patient_info['excel_data']['address']}\n"
                        )

                        f.write(
                            f"   Существующий пациент в базе (ID: {patient_info['db_data']['id']}):\n"
                        )
                        f.write(f"     • ФИО: {patient_info['db_data']['full_name']}\n")
                        f.write(
                            f"     • Номер карты: {patient_info['db_data']['card_number']}\n"
                        )
                        f.write(
                            f"     • Дата рождения: {patient_info['db_data']['date_of_birth']}\n"
                        )
                        f.write(f"     • Телефон: {patient_info['db_data']['phone']}\n")
                        f.write(f"     • Адрес: {patient_info['db_data']['address']}\n")

                        f.write(f"   ПРИЧИНА: {patient_info['reason']}\n")
                        f.write(
                            f"   ДЕЙСТВИЕ: Проверить в админке или БД, один ли это пациент.\n"
                        )
                        f.write(
                            f"             Если да - добавить номер карты {patient_info['excel_data']['card_number']} и другие данные.\n"
                        )
                        f.write(
                            f"             Если нет - оставить как отдельные записи.\n"
                        )
                        f.write("\n" + "-" * 60 + "\n")

                    f.write(
                        f"\nВсего пациентов для проверки: {len(manual_check_patients)}\n"
                    )

                print(f"\nОтчет сохранен в файл: {report_file}")
            except Exception as e:
                print(f"Ошибка при сохранении отчета: {e}")

        return stats

    except FileNotFoundError:
        print(f"Ошибка: файл {file_path} не найден")
        print(f"Текущая директория: {os.getcwd()}")
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
        import traceback

        traceback.print_exc()


def backup_patients():
    """Создание резервной копии перед импортом"""
    from django.core import serializers
    import time

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_file = f"patients_backup_{timestamp}.json"

    try:
        patients = Patient.objects.all()
        with open(backup_file, "w", encoding="utf-8") as f:
            serializers.serialize("json", patients, stream=f, indent=2)
        print(f"Создана резервная копия: {backup_file}")
        print(f"Всего пациентов в БД до импорта: {patients.count()}")
        return backup_file
    except Exception as e:
        print(f"Ошибка при создании резервной копии: {e}")
        return None


if __name__ == "__main__":
    excel_file_path = "C:/Users/user/PycharmProjects/Revmamed/test_data_for_db.xlsx"

    if not os.path.exists(excel_file_path):
        print(f"Файл не найден: {excel_file_path}")
        print("Проверьте путь и имя файла")
    else:
        print(f"Файл найден: {excel_file_path}")
        print(f"Размер файла: {os.path.getsize(excel_file_path)} байт")

        print("\nСоздание резервной копии...")
        backup_file = backup_patients()

        print("\n" + "=" * 50)
        print("НАЧИНАЕМ ИМПОРТ ДАННЫХ...")
        print("=" * 50)

        import_patients_from_excel(excel_file_path)

        print("\nИмпорт завершен!")
