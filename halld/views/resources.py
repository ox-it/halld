import http.client

from django.db import transaction
from rest_framework.response import Response
import rest_framework.renderers

from .base import HALLDView
from ..models import Resource
from .. import exceptions
from .. import renderers
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

    def get_template_names(self):
        return ['halld/resource-type/' + self.kwargs['resource_type'] + '.html',
                'halld/resource-type.html']

    def get(self, request, resource_type):
        resources = Resource.objects.filter(type_id=self.resource_type.name)
        if self.exclude_extant:
            resources = resources.filter(extant=False)
        if self.exclude_defunct:
            resources = resources.filter(extant=True)
        paginator, page = self.get_paginator_and_page(resources)
        return Response(response_data.ResourceList(paginator=paginator,
                                                   page=page,
                                                   resource_type=self.resource_type,
                                                   exclude_extant=self.exclude_extant,
                                                   exclude_defunct=self.exclude_defunct,
                                                   user=request.user,
                                                   object_cache=request.object_cache))

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

    def get_template_names(self):
        return ['halld/resource/' + self.kwargs['resource_type'] + '.html',
                'halld/resource.html']

    def get(self, request, resource_type, identifier):
        resource = request.object_cache.resource.get(self.href)
        if resource.deleted:
            raise exceptions.DeletedResource()
        return Response(response_data.Resource({
            'resource': resource,
            'filtered_data': resource.get_filtered_data(request.user, resource.data),
            'resource_type': resource_type,
            'user': request.user,
            'object_cache': request.object_cache,
        }))

    @transaction.atomic
    def post(self, request, resource_type, identifier):
        resource = Resource.create(request.user, self.resource_type, identifier)
        return Response('', headers={'Location': resource.href}, status=http.client.CREATED)
