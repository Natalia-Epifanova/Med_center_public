from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from .models import Patient


@csrf_exempt
@require_http_methods(["POST"])
def check_patient_api(request):
    """API для проверки существования пациента"""
    try:
        data = json.loads(request.body)
        surname = data.get("surname", "").strip()
        first_name = data.get("first_name", "").strip()
        date_of_birth = data.get("date_of_birth", "")

        if not surname or not first_name:
            return JsonResponse(
                {"error": "Фамилия и имя обязательны для проверки"}, status=400
            )

        # Поиск пациента
        patients = Patient.objects.filter(
            surname__iexact=surname, first_name__iexact=first_name
        )

        if date_of_birth:
            patients = patients.filter(date_of_birth=date_of_birth)

        existing_patient = patients.first()

        if existing_patient:
            return JsonResponse(
                {
                    "exists": True,
                    "patient": {
                        "id": existing_patient.id,
                        "full_name": existing_patient.get_full_name(),
                        "card_number": existing_patient.card_number,
                        "phone_number": existing_patient.phone_number,
                        "date_of_birth": (
                            existing_patient.date_of_birth.isoformat()
                            if existing_patient.date_of_birth
                            else None
                        ),
                    },
                }
            )
        else:
            return JsonResponse({"exists": False})

    except Exception as e:
        return JsonResponse({"error": f"Ошибка сервера: {str(e)}"}, status=500)
