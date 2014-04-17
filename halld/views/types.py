from django.http import Http404

from .base import HALLDView
from ..registry import get_resource_type

__all__ = ['ResourceTypeListView', 'ResourceTypeDetailView']

class ResourceTypeListView(HALLDView):
    def get(self, request, resource_type):
        return self.render()

class ResourceTypeDetailView(HALLDView):
    def dispatch(self, request, resource_type, **kwargs):
        try:
            resource_type = get_resource_type(resource_type)
        except KeyError:
            raise Http404
        return super(ResourceTypeDetailView, self).dispatch(request, resource_type, **kwargs)

    def get(self, request, resource_type):
        self.context.update(resource_type.get_type_properties())
        self.context.update({
            '@id': '',
            'id': resource_type.name,
            'label': resource_type.label,
            'labelPlural': resource_type.label_plural,
        })
        return self.render()
