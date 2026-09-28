from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        import accounts.signals

        # Pillow can't decode HEIC/HEIF (the default format for iPhone photos)
        # without this. Registering it here -- not in accounts.utils -- makes it
        # take effect before Django's ImageField validation, which also opens
        # the upload with Pillow (in forms.py's clean()), not just our own
        # process_avatar().
        from pillow_heif import register_heif_opener
        register_heif_opener()
