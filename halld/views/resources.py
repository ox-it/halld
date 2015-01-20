import http.client

from django.db import transaction
from rest_framework.response import Response

from .base import HALLDView
from ..models import Resource
from .. import exceptions
from halld import response_data

__all__ = ['ResourceListView', 'ResourceDetailView']

class ResourceListView(HALLDView):
    def initial(self, request, resource_type):
        super().initial(request, resource_type)

        try:
            self.resource_type = self.halld_config.resource_types[resource_type]
        except KeyError:
            raise exceptions.NoSuchResourceType(resource_type)
        self.exclude_extant = request.GET.get('extant', 'on') == 'off'
        self.exclude_defunct = request.GET.get('defunct', 'off') == 'off'

    def get(self, request, resource_type):
        resources = Resource.objects.filter(type_id=self.resource_type.name)
        if self.exclude_extant:
            resources = resources.filter(extant=False)
        if self.exclude_defunct:
            resources = resources.filter(extant=True)
        return Response(response_data.ResourceList(resources, self.resource_type,
                                                   exclude_extant=self.exclude_extant,
                                                   exclude_defunct=self.exclude_defunct))

    @transaction.atomic
    def post(self, request, resource_type):
        resource = Resource.create(request.user, resource_type)
        return Response('', headers={'Location': resource.href}, status=http.client.CREATED)

class ResourceDetailView(HALLDView):
    def initial(self, request, resource_type, identifier):
        super().initial(request, resource_type)
        try:
            self.resource_type = self.halld_config.resource_types[resource_type]
        except KeyError:
            raise exceptions.NoSuchResourceType(resource_type)
        if not self.resource_type.is_valid_identifier(identifier):
            raise exceptions.NotValidIdentifier(identifier)
        self.href = self.resource_type.base_url + identifier

    def get(self, request, resource_type, identifier):
        resource = request.object_cache.resource.get(self.href)
        if resource.deleted:
            raise exceptions.DeletedResource()
        return Response(response_data.Resource(resource))

    @transaction.atomic
    def post(self, request, resource_type, identifier):
        resource = Resource.create(request.user, self.resource_type, identifier)
        return Response('', headers={'Location': resource.href}, status=http.client.CREATED)
