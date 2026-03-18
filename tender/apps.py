# apps.py
# tender/apps.py
from django.apps import AppConfig

class TenderConfig(AppConfig):
    name = 'tender'

    def ready(self):
        import tender.handlers  # 👈 this wires up the receivers