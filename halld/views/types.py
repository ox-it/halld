from django.http import Http404

from .. import get_halld_config
from .base import HALLDView

__all__ = ['ResourceTypeListView', 'ResourceTypeDetailView']

class ResourceTypeView(HALLDView):
    def resource_type_as_hal(self, resource_type):
        hal = {
            'id': resource_type.name,
            'label': resource_type.label,
            'labelPlural': resource_type.label_plural,
        }
        hal.update(resource_type.get_type_properties())
        return hal

class ResourceTypeListView(ResourceTypeView):
    def get(self, request, *args, **kwargs):
        self.context['resource_types'] = get_halld_config().resource_types
        return self.render()

    def hal_json_from_context(self, request, context):
        hal = {
            '@id': '',
            '_embedded': {
                'item': [self.resource_type_as_hal(resource_type)
                         for resource_type in context['resource_types'].values()]
            }
        }
        return hal

class ResourceTypeDetailView(ResourceTypeView):
    def dispatch(self, request, resource_type, **kwargs):
        try:
            resource_type = get_halld_config().resource_types[resource_type]
        except KeyError:
            raise Http404
        return super(ResourceTypeDetailView, self).dispatch(request, resource_type, **kwargs)

    def get(self, request, resource_type):
        self.context['resource_type'] = resource_type
        return self.render()

    def hal_json_from_context(self, request, context):
        hal = {'@id': ''}
        hal.update(self.resource_type_as_hal(context['resource_type']))
        return hal
