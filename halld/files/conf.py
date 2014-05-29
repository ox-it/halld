from django.conf import settings

USE_XSENDFILE = getattr(settings, 'USE_XSENDFILE', False)
FILE_METADATA_USER = getattr(settings, 'FILE_METADATA_USER')