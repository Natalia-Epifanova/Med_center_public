def number_to_words(num):
    """Преобразует число в слова (рубли)"""
    # Словари для преобразования
    units = [
        "",
        "один",
        "два",
        "три",
        "четыре",
        "пять",
        "шесть",
        "семь",
        "восемь",
        "девять",
    ]
    teens = [
        "десять",
        "одиннадцать",
        "двенадцать",
        "тринадцать",
        "четырнадцать",
        "пятнадцать",
        "шестнадцать",
        "семнадцать",
        "восемнадцать",
        "девятнадцать",
    ]
    tens = [
        "",
        "",
        "двадцать",
        "тридцать",
        "сорок",
        "пятьдесят",
        "шестьдесят",
        "семьдесят",
        "восемьдесят",
        "девяносто",
    ]
    hundreds = [
        "",
        "сто",
        "двести",
        "триста",
        "четыреста",
        "пятьсот",
        "шестьсот",
        "семьсот",
        "восемьсот",
        "девятьсот",
    ]
    thousands = ["", "тысяча", "тысячи", "тысяч"]

    if num == 0:
        return "ноль рублей"

    def convert_three_digits(n):
        """Конвертирует трехзначное число"""
        result = []

        # Сотни
        if n >= 100:
            result.append(hundreds[n // 100])
            n %= 100

        # Десятки и единицы
        if n >= 20:
            result.append(tens[n // 10])
            if n % 10 > 0:
                result.append(units[n % 10])
        elif n >= 10:
            result.append(teens[n - 10])
        elif n > 0:
            result.append(units[n])

        return " ".join(result)

    # Основная логика
    words = []

    # Тысячи
    if num >= 1000:
        thousands_part = num // 1000
        if thousands_part == 1:
            words.append("одна тысяча")
        elif thousands_part == 2:
            words.append("две тысячи")
        elif thousands_part in [3, 4]:
            words.append(convert_three_digits(thousands_part) + " тысячи")
        else:
            words.append(convert_three_digits(thousands_part) + " тысяч")
        num %= 1000

    # Сотни, десятки, единицы
    if num > 0 or not words:  # Если число было меньше 1000
        words.append(convert_three_digits(num))

    result = " ".join(words)
    return result.strip()


def get_russian_month_name(month_number):
    """Возвращает русское название месяца по номеру"""
    months = {
        1: "января",
        2: "февраля",
        3: "марта",
        4: "апреля",
        5: "мая",
        6: "июня",
        7: "июля",
        8: "августа",
        9: "сентября",
        10: "октября",
        11: "ноября",
        12: "декабря",
    }
    return months.get(month_number, "")
