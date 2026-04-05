import os
import sys

from waitress import serve

# Add project path explicitly.
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_dir not in sys.path:
    sys.path.append(project_dir)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application


if __name__ == "__main__":
    print("=" * 50)
    print("Starting Django MedCenter in production mode")
    print("Waitress listens only on localhost:8000")
    print("External access goes through nginx")
    print("=" * 50)

    serve(
        application,
        host="127.0.0.1",
        port=8000,
        threads=4,
        channel_timeout=120,
        cleanup_interval=30,
    )
