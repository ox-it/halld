from django.core.urlresolvers import reverse

from .. import get_halld_config
from .base import HALLDView
from halld.response_data import Index
from rest_framework.response import Response

__all__ = ['IndexView']

class IndexView(HALLDView):
    template_name = 'halld/index.html'

    def get(self, request):
        links = {
            'findResourceType': {'href': '/type/{resourceType}',
                           'templated': True},
            'findResourceList': {'href': '/{resourceType}',
                           'templated': True},
            'findResource': {'href': '/{resourceType}/{identifier}',
                           'templated': True},
            'findSource': {'href': '/{resourceType}/{identifier}/source/{source}',
                           'templated': True},
            'findByIdentifier': {'href': reverse('halld:by-identifier')},
            'graph': {'href': reverse('halld:graph')},
            'changeset': {'href': reverse('halld:changeset-list')},
        }
        links.update({
            'items:{}'.format(resource_type.name): {
                'href': reverse('halld:resource-list', args=[resource_type.name])}
            for resource_type in get_halld_config().resource_types.values()
        })
        links.update({
            'type:{}'.format(resource_type.name): {
                'href': reverse('halld:resource-type-detail', args=[resource_type.name])}
            for resource_type in get_halld_config().resource_types.values()
        })
        return Response(Index(links=links))

    def hal_json_from_context(self, request, context):
        hal = {'_links': {}}
        hal['_links'].update({
            'findResourceType': {'href': '/type/{resourceType}',
                           'templated': True},
            'findResourceList': {'href': '/{resourceType}',
                           'templated': True},
            'findResource': {'href': '/{resourceType}/{identifier}',
                           'templated': True},
            'findSource': {'href': '/{resourceType}/{identifier}/source/{source}',
                           'templated': True},
            'findByIdentifier': {'href': reverse('halld:by-identifier')},
            'graph': {'href': reverse('halld:graph')},
            'changeset': {'href': reverse('halld:changeset-list')},
        })
        hal['_links'].update({
            'items:{}'.format(resource_type.name): {
                'href': reverse('halld:resource-list', args=[resource_type.name])}
            for resource_type in get_halld_config().resource_types.values()
        })
        hal['_links'].update({
            'type:{}'.format(resource_type.name): {
                'href': reverse('halld:resource-type-detail', args=[resource_type.name])}
            for resource_type in get_halld_config().resource_types.values()
        })
        return hal
