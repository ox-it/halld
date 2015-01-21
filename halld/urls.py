from django.conf.urls import patterns, url

from . import views

urlpatterns = patterns('',
    url(r'^$',
        views.IndexView.as_view(),
        name='index'),
    url(r'^by-identifier$',
        views.ByIdentifierView.as_view(),
        name='by-identifier'),
    url(r'^graph$',
        views.GraphView.as_view(),
        name='graph'),
    url(r'^changeset$',
        views.ChangesetListView.as_view(),
        name='changeset-list'),
    url(r'^regenerate-all$',
        views.RegenerateAllView.as_view(),
        name='regenerate-all'),

    url(r'^type$',
        views.ResourceTypeListView.as_view(),
        name='resource-type-list'),
    url(r'^type/(?P<resource_type>[a-z\-]+)$',
        views.ResourceTypeDetailView.as_view(),
        name='resource-type-detail'),

    url(r'^(?P<resource_type>[a-z\-]+)$',
        views.ResourceListView.as_view(),
        name='resource-list'),
    url(r'^(?P<resource_type>[a-z\-]+)/(?P<identifier>[a-z\-\d]+)$',
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