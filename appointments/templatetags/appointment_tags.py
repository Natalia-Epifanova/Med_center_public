from django import template
from appointments.models import Appointment

register = template.Library()


@register.simple_tag(name="get_appointment")
def get_appointment_for_slot(slot):
    """Возвращает первую запись для указанного слота"""
    try:
        return Appointment.objects.filter(time_slot=slot).first()
    except Exception:
        return None


@register.filter
def has_appointment(slot):
    """Проверяет, есть ли запись у слота"""
    try:
        return Appointment.objects.filter(time_slot=slot).exists()
    except Exception:
        return False
