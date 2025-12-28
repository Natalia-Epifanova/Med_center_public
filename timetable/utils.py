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
