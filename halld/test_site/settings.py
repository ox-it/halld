SECRET_KEY = 'secret'

TIME_ZONE = 'Europe/London'
USE_TZ = True

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.sites',
    'django.contrib.contenttypes',
    'halld.test_site.apps.TestHALLDConfig',
    'halld.files',
    'halld.test_site',
    'rest_framework',
]

BASE_URL = 'http://testserver/'

ROOT_URLCONF = 'halld.test_site.urls'

FILE_METADATA_USER = 'file-metadata'

MIDDLEWARE_CLASSES = (
)

REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'halld.test_site.exceptions.reraise',
    'TEST_REQUEST_DEFAULT_FORMAT': 'hal-json',
}
