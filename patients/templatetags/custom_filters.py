from django import template

register = template.Library()


@register.filter
def split(value, delimiter=" "):
    """Разделяет строку по разделителю"""
    return value.split(delimiter)
