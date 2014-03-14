SECRET_KEY = 'secret'

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.sites',
    'django.contrib.contenttypes',
    'halld',
    'halld.test_site',
    'django_conneg',
]

RESOURCE_TYPES = [
    'halld.test_site.registry.SnakeResourceTypeDefinition',
    'halld.test_site.registry.PenguinResourceTypeDefinition',
]

from halld.registry import LinkTypeDefinition, SourceTypeDefinition

LINK_TYPES = [
    LinkTypeDefinition.new('eats', 'eatenBy'),
]

SOURCE_TYPES = [
    SourceTypeDefinition.new('science'),
    SourceTypeDefinition.new('mythology'),
]

BASE_URL = 'http://testserver/'

ROOT_URLCONF = 'halld.test_site.urls'
