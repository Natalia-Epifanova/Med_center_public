from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


class MedicalStaffRequiredMixin(AccessMixin):
    """Миксин для допуска суперпользователей, администраторов, медадминов и врачей"""

    allowed_groups = ["Medical Center Administrator", "Admin", "Doctors"]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        is_allowed = request.user.is_superuser or request.user.groups.filter(
            name__in=self.allowed_groups
        ).exists()

        if not is_allowed:
            raise PermissionDenied("У вас нет прав для доступа к этой странице")

        return super().dispatch(request, *args, **kwargs)


class MedicalAdminOrAdminRequiredMixin(AccessMixin):
    """Миксин для проверки принадлежности к группе Medical Center Administrator или Admin"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if not (
            request.user.groups.filter(name="Medical Center Administrator").exists()
            or request.user.groups.filter(name="Admin").exists()
        ):
            raise PermissionDenied("У вас нет прав для доступа к этой странице")

        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(AccessMixin):
    """Миксин для проверки принадлежности к группе Admin"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Проверяем принадлежность к группе "Admin"
        if not request.user.groups.filter(name="Admin").exists():
            raise PermissionDenied(
                "У вас нет прав для доступа к этой странице. Только для администраторов системы."
            )

        return super().dispatch(request, *args, **kwargs)
