import abc

from django.apps.config import AppConfig
from django.conf import settings

class HALLDFilesConfig(AppConfig, metaclass=abc.ABCMeta):
    name = 'halld.files'
    verbose_name = 'HAL-LD files'


    use_xsendfile = getattr(settings, 'USE_XSENDFILE', False)
    file_metadata_user = 'file-metadata'
