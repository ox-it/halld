import re

from django.conf.urls import url, patterns

from . import views
from .. import get_halld_config
from .definitions.resources import FileResourceTypeDefinition

# Only match for file resources
halld_config = get_halld_config()
file_resource_type_names = [n for (n, rt)
                            in halld_config.resource_types.items()
                            if isinstance(rt, FileResourceTypeDefinition)]
pattern = '|'.join(re.escape(name) for name in file_resource_type_names)

urlpatterns = patterns('',
    url(r'^(?P<resource_type>(?:{}))$'.format(pattern),
        views.FileCreationView.as_view(),
        name='file-create'),
    url(r'^(?P<resource_type>(?:{}))/(?P<identifier>[a-z\-\d]+)/file$'.format(pattern),
        views.FileDetailView.as_view(),
        name='file-detail'),
)