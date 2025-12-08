from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def medical_admin_or_admin_required(view_func):
    """Декоратор для проверки прав Medical Center Administrator или Admin"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("users:login")

        if not (
            request.user.groups.filter(name="Medical Center Administrator").exists()
            or request.user.groups.filter(name="Admin").exists()
        ):
            raise PermissionDenied("У вас нет прав для выполнения этого действия")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def admin_required(view_func):
    """Декоратор для проверки прав группы Admin"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("users:login")

        # Проверяем принадлежность к группе "Admin"
        if not request.user.groups.filter(name="Admin").exists():
            raise PermissionDenied(
                "У вас нет прав для выполнения этого действия. Только для администраторов системы."
            )

        return view_func(request, *args, **kwargs)

    return _wrapped_view
