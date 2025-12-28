class StyleFormMixin:
    """Миксин для стилизации форм"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if "class" not in field.widget.attrs:
                field.widget.attrs["class"] = "form-control"


# class ServiceBasedFormMixin:
#     """Миксин для форм, зависящих от услуг врача"""
#
#     def __init__(self, *args, **kwargs):
#         self.doctor = kwargs.pop("doctor", None)
#         super().__init__(*args, **kwargs)
#
#         if self.doctor:
#             services = self.doctor.get_available_services()
#             self.fields["service"].queryset = services
#             if "additional_service" in self.fields:
#                 self.fields["additional_service"].queryset = services
