from django.http import Http404
from rest_framework.response import Response

from .. import get_halld_config
from .. import response_data
from .base import HALLDView

__all__ = ['ResourceTypeListView', 'ResourceTypeDetailView']

class ResourceTypeView(HALLDView):
    pass

class ResourceTypeListView(ResourceTypeView):
    def get(self, request, *args, **kwargs):
        return Response(response_data.ResourceTypeList(self.halld_config.resource_types))

class ResourceTypeDetailView(ResourceTypeView):
    def initial(self, request, resource_type):
        super().initial(request, resource_type)
        try:
            self.resource_type = self.halld_config.resource_types[resource_type]
        except KeyError:
            raise Http404

    def get(self, request, resource_type):
        return Response(response_data.ResourceType(self.response_type))

