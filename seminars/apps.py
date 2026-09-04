from django.apps import AppConfig


class SeminarsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'seminars'
    # The admin groups models under this label; the public site calls this
    # vertical "Visits" everywhere, so match it there too.
    verbose_name = 'Visits'
