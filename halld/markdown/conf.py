from django.conf import settings

try:
    MARKDOWN_PARAMS = settings.MARKDOWN_PARAMS
except AttributeError:
    MARKDOWN_PARAMS = {
        'safe_mode': 'remove',
        'output_format': 'html5',
        'extensions': ['sane_lists', 'codehilite', 'extra'],
    }
