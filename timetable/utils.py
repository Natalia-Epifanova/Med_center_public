from .models import MedicalService


def get_doctor_services(doctor, include_current_service=None):
    """Получает услуги, доступные для врача"""
    from django.db.models import Q

    if not doctor:
        return MedicalService.objects.filter(is_active=True)

    # Получаем категории услуг, которые оказывает врач
    provided_categories = doctor.provided_services

    # Получаем исключенные услуги
    excluded_service_ids = doctor.excluded_services.values_list("id", flat=True)

    # Фильтруем услуги по категориям врача и исключаем недоступные
    services_queryset = MedicalService.objects.filter(
        category__in=provided_categories, is_active=True
    ).exclude(id__in=excluded_service_ids)

    # Включаем текущую услугу если указана
    if include_current_service:
        services_queryset = (
            MedicalService.objects.filter(
                Q(id=include_current_service.id)
                | Q(category__in=provided_categories, is_active=True)
            )
            .exclude(Q(id__in=excluded_service_ids) & ~Q(id=include_current_service.id))
            .distinct()
        )

    return services_queryset


def get_status_badge_class(status):
    """Получить CSS класс для бейджа статуса"""
    status_classes = {
        "scheduled": "bg-primary",
        "confirmed": "bg-info",
        "completed": "bg-success",
        "cancelled": "bg-warning",
        "no_show": "bg-danger",
    }
    return status_classes.get(status, "bg-secondary")
