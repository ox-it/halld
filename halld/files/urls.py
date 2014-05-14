from django.conf.urls import url, patterns

from . import views

urlpatterns = patterns('',
    url(r'^(?P<resource_type>[a-z\-]+)$',
        views.FileCreationView.as_view(),
        name='file-create'),
    url(r'^(?P<resource_type>[a-z\-]+)/(?P<identifier>[a-z\-\d]+)/file$',
        views.FileView.as_view(),
        name='file-detail'),
)