from django.apps import apps as django_apps

default_app_config = 'halld.files.apps.HALLDFilesConfig'

def get_halld_files_config():
    return django_apps.get_app_config('files')

