from django.core.urlresolvers import reverse
from django_conneg.views import HTMLView

from .base import HALLDView
from ..registry import get_resource_types

__all__ = ['IndexView']

class IndexView(HALLDView, HTMLView):
    template_name = 'index'

    def get(self, request):
        return self.render()

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
        })
        hal['_links'].update({
            'items:{}'.format(resource_type.name): {
                'href': reverse('halld:resource-list', args=[resource_type.name])}
            for resource_type in get_resource_types().values()
        })
        hal['_links'].update({
            'type:{}'.format(resource_type.name): {
                'href': reverse('halld:resource-type-detail', args=[resource_type.name])}
            for resource_type in get_resource_types().values()
        })
        return hal
