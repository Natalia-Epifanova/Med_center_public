from django import template
from patients.utils import get_russian_month_name

register = template.Library()


@register.filter
def get_russian_month_name_filter(month_num):
    """Возвращает название месяца на русском с заглавной буквы"""
    month_name = get_russian_month_name(month_num)
    return month_name.capitalize() if month_name else ""


@register.filter
def month_range(value):
    """Создает диапазон от 1 до value"""
    return range(1, int(value) + 1)


@register.filter
def to_int(value):
    """Конвертирует в целое число"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
