from django.apps import AppConfig


class MenudConfig(AppConfig):
    name = 'Aplicacion.Menud'

class MenudConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Aplicacion.Menud'

    def ready(self):
        import Aplicacion.Menud.signals
