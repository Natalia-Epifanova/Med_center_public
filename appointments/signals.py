from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from appointments.models import Appointment
from timetable.models import TimeSlot

from appointments.utils import clear_doctor_slots_cache


@receiver([post_save, post_delete], sender=Appointment)
def clear_slots_cache_on_appointment_change(sender, instance, **kwargs):
    """Очистить кэш слотов при изменении записи"""
    if hasattr(instance, "time_slot") and instance.time_slot:
        clear_doctor_slots_cache(
            doctor_id=instance.time_slot.doctor_id, date=instance.time_slot.date
        )


@receiver([post_save, post_delete], sender=TimeSlot)
def clear_slots_cache_on_slot_change(sender, instance, **kwargs):
    """Очистить кэш слотов при изменении слота"""
    clear_doctor_slots_cache(doctor_id=instance.doctor_id, date=instance.date)
