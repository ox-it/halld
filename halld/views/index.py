from django.core.urlresolvers import reverse

from .base import HALLDView
from ..registry import get_resource_types

__all__ = ['IndexView']

class IndexView(HALLDView):
    def get(self, request):
        self.context['_links'] = {
            'type:{}'.format(resource_type.name): {
                'href': reverse('halld:resource-type', args=[resource_type.name])}
            for resource_type in get_resource_types().values()
        }
        self.context['_links'].update({
            'findResourceType': {'href': '/{resourceType}',
                           'templated': True},
            'findResource': {'href': '/{resourceType}/{identifier}',
                           'templated': True},
            'findSource': {'href': '/{resourceType}/{identifier}/source/{source}',
                           'templated': True},
            'findByIdentifier': {'href': reverse('halld:by-identifier')}
        })
        return self.render()
