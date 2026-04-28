import logging

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from appointments.models import Appointment
from appointments.utils_for_caches import clear_doctor_slots_cache
from timetable.models import TimeSlot

logger = logging.getLogger(__name__)


def clear_doctor_schedule_dates_cache_for_date(target_date):
    """Очистить кэш дат приема врачей для месяца указанной даты."""
    if not target_date:
        return

    cache.delete(f"doctor_schedule_dates_{target_date.year}_{target_date.month}")


@receiver([post_save, post_delete], sender=Appointment)
def clear_slots_cache_on_appointment_change(sender, instance, **kwargs):
    """Очистить кэш слотов при изменении записи"""
    try:
        if hasattr(instance, "time_slot") and instance.time_slot:
            logger.info(
                "Очистка кэша слотов после изменения записи: appointment_id=%s patient_id=%s doctor_id=%s date=%s signal=%s",
                instance.id,
                getattr(instance, "patient_id", None),
                instance.time_slot.doctor_id,
                instance.time_slot.date,
                "post_save/post_delete",
            )
            clear_doctor_slots_cache(
                doctor_id=instance.time_slot.doctor_id,
                date=instance.time_slot.date,
            )
            clear_doctor_schedule_dates_cache_for_date(instance.time_slot.date)
        else:
            logger.warning(
                "Не удалось очистить кэш слотов после изменения записи: appointment_id=%s reason=no_time_slot",
                getattr(instance, "id", None),
            )
    except Exception:
        logger.exception(
            "Ошибка при очистке кэша слотов после изменения записи: appointment_id=%s",
            getattr(instance, "id", None),
        )


@receiver([post_save, post_delete], sender=TimeSlot)
def clear_slots_cache_on_slot_change(sender, instance, **kwargs):
    """Очистить кэш слотов при изменении слота"""
    try:
        logger.info(
            "Очистка кэша слотов после изменения TimeSlot: slot_id=%s doctor_id=%s date=%s signal=%s",
            instance.id,
            instance.doctor_id,
            instance.date,
            "post_save/post_delete",
        )
        clear_doctor_slots_cache(doctor_id=instance.doctor_id, date=instance.date)
        clear_doctor_schedule_dates_cache_for_date(instance.date)
    except Exception:
        logger.exception(
            "Ошибка при очистке кэша слотов после изменения TimeSlot: slot_id=%s",
            getattr(instance, "id", None),
        )
