from django.apps import apps as django_apps

default_app_config = 'halld.apps.HALLDConfig'

def get_halld_config():
    return django_apps.get_app_config('halld')

