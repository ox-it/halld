SECRET_KEY = 'secret'

TIME_ZONE = 'Europe/London'
USE_TZ = True

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.sites',
    'django.contrib.contenttypes',
    'halld',
    'halld.files',
    'halld.test_site',
    'django_conneg',
]

RESOURCE_TYPES = [
    'halld.test_site.registry.DocumentResourceTypeDefinition',
    'halld.test_site.registry.SnakeResourceTypeDefinition',
    'halld.test_site.registry.PenguinResourceTypeDefinition',
]

from halld.registry import LinkTypeDefinition, SourceTypeDefinition

LINK_TYPES = [
    LinkTypeDefinition.new('eats', 'eatenBy'),
    LinkTypeDefinition.new('timelessF', 'timelessR', timeless=True)
]

SOURCE_TYPES = [
    'halld.files.metadata.ImageMetadataSourceTypeDefinition',
    SourceTypeDefinition.new('science'),
    SourceTypeDefinition.new('mythology'),
]

BASE_URL = 'http://testserver/'

ROOT_URLCONF = 'halld.test_site.urls'

FILE_METADATA_USER = 'file-metadata'