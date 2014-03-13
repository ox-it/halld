from django.conf.urls import patterns, url

from . import views

format_re = r'(?:\.(?P<format>[a-z\d]+))?$'

urlpatterns = patterns('',
    url(r'^' + format_re,
        views.IndexView.as_view(),
        name='index'),
    url(r'^(?P<resource_type>[a-z\-]+)' + format_re,
        views.ResourceTypeView.as_view(),
        name='resource-type'),
    url(r'^(?P<resource_type>[a-z\-]+)/(?P<identifier>[a-z\-\d]+)' + format_re,
        views.ResourceView.as_view(),
        name='resource'),
    url(r'^(?P<resource_type>[a-z\-]+)/(?P<identifier>[a-z\-\d]+)/source$',
        views.SourceListView.as_view(),
        name='source-list'),
    url(r'^(?P<resource_type>[a-z\-]+)/(?P<identifier>[a-z\-\d]+)/source/(?P<source_type>[a-z\i\d:\-]+)$',
        views.SourceDetailView.as_view(),
        name='source-detail'),
    
    url(r'^id/(?P<resource_type>[a-z\-]+)/(?P<identifier>[a-z\-\d]+)$',
        views.IdView.as_view(),
        name='id'),
)