from django import template

register = template.Library()


@register.filter
def get_by_key(value, arg):
    """Получить значение из словаря по ключу"""
    return value.get(arg, {})
