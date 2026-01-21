def user_permissions(request):
    """Добавляет флаги прав в контекст шаблонов"""
    if not request.user.is_authenticated:
        return {}

    return {
        "is_admin": request.user.groups.filter(name="Admin").exists(),
        "is_medical_admin": request.user.groups.filter(
            name="Medical Center Administrator"
        ).exists(),
        "is_doctor": request.user.groups.filter(name="Doctors").exists(),
        "can_manage_schedule": request.user.groups.filter(name="Admin").exists(),
        "can_create_emergency_slots": request.user.groups.filter(
            name="Medical Center Administrator"
        ).exists(),
    }
