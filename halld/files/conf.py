from django.conf import settings

USE_XSENDFILE = getattr(settings, 'USE_XSENDFILE', False)