import os
import sys

from waitress import serve

from config.wsgi import application


sys.path.append(os.path.dirname(os.path.abspath(__file__)))


if __name__ == "__main__":
    print("=" * 50)
    print("Запуск Django MedCenter в режиме продакшена")
    print("Сервер: http://0.0.0.0:8000")
    print("Доступ с других компьютеров настраивается через сетевую конфигурацию")
    print("=" * 50)

    serve(
        application,
        host="0.0.0.0",
        port=8000,
        threads=4,
        channel_timeout=120,
        cleanup_interval=30,
    )
