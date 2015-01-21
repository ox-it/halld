from django.conf.urls import patterns, url

from . import views

format_re = r'(?:\.(?P<format>[a-z\d]+))?$'

urlpatterns = patterns('',
    url(r'^' + format_re,
        views.IndexView.as_view(),
        name='index'),
    url(r'^by-identifier$',
        views.ByIdentifierView.as_view(),
        name='by-identifier'),
    url(r'^graph' + format_re,
        views.GraphView.as_view(),
        name='graph'),
    url(r'^changeset$',
        views.ChangesetListView.as_view(),
        name='changeset-list'),
    url(r'^regenerate-all$',
        views.RegenerateAllView.as_view(),
        name='regenerate-all'),

    url(r'^type' + format_re,
        views.ResourceTypeListView.as_view(),
        name='resource-type-list'),
    url(r'^type/(?P<resource_type>[a-z\-]+)' + format_re,
        views.ResourceTypeDetailView.as_view(),
        name='resource-type-detail'),

    url(r'^(?P<resource_type>[a-z\-]+)' + format_re,
        views.ResourceListView.as_view(),
        name='resource-list'),
    url(r'^(?P<resource_type>[a-z\-]+)/(?P<identifier>[a-z\-\d]+)' + format_re,
        views.ResourceDetailView.as_view(),
        name='resource-detail'),

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