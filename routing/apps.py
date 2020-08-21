from django.apps import AppConfig


class RoutingConfig(AppConfig):
    name = 'routing'

    def ready(self):
        import routing.signals
