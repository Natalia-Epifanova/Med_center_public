import sys
import os
from waitress import serve
from config.wsgi import application

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    print("=" * 50)
    print("Запуск Django MedCenter в режиме продакшена")
    print("Сервер: http://0.0.0.0:8000")
    print("Доступ с других компьютеров: http://192.168.8.180")
    print("=" * 50)

    # Запускаем Waitress с настройками для продакшена
    serve(
        application,
        host='0.0.0.0',
        port=8000,
        threads=4,
        channel_timeout=120,
        cleanup_interval=30
    )