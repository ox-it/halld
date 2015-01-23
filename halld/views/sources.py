import http.client
import json
from time import mktime
import wsgiref.handlers

from django.core.urlresolvers import reverse
from django.db import transaction
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseNotModified
from rest_framework.response import Response

from .mixins import VersioningMixin
from .. import exceptions, get_halld_config
from .. import response_data
from ..models import Source, Resource, Changeset
from .changeset import ChangesetView
import jsonschema

__all__ = ['SourceListView', 'SourceDetailView']

class BulkSourceUpdateView(ChangesetView):
    @method_decorator(login_required)
    def post(self):
        raise NotImplementedError

class SourceListView(ChangesetView):
    def initial(self, request, resource_type, identifier):
        super().initial(request, resource_type, identifier)
        try:
            self.resource_type = self.halld_config.resource_types[resource_type]
        except KeyError:
            raise exceptions.NoSuchResourceType(resource_type)
        self.resource_href = self.resource_type.base_url + identifier
        if not Resource.objects.filter(href=self.resource_href).exists():
            raise exceptions.SourceDataWithoutResource(resource_type, identifier)

    def get(self, request, resource_type, identifier):
        sources = Source.objects.filter(resource_id=self.resource_href)
        visible_sources = [source for source in sources
                                  if not source.deleted and
                                     request.user.has_perm('halld.view_source', source)]
        paginator, page = self.get_paginator_and_page(visible_sources)
        return Response(response_data.SourceList(sources=visible_sources,
                                                 paginator=paginator,
                                                 page=page))

    put_schema = {
        'properties': {
            '_embedded': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'item': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                '_meta': {
                                    'type': 'object',
                                    'properties': {
                                        'sourceType': {'type': 'string'},
                                    },
                                },
                            },
                        },
                    },
                },
            }
        },
    }

    def put(self, request, resource_type, identifier):
        data = self.get_request_json('application/hal+json')
        try:
            jsonschema.validate(data, self.put_schema)
        except jsonschema.ValidationError as e:
            raise exceptions.SchemaValidationError(e)
        items = data.get('_embedded', {}).get('item')

        updates, source_types = [], set()
        for item in items:
            source_type = item['_meta']['sourceType']

            source_types.add(source_type)
            item.pop('_links', None)
            item.pop('_meta', None)

            updates.append({
                'method': 'PUT',
                'sourceType': source_type,
                'resourceHref': self.resource_href,
                'data': item,
            })

        source_types_to_delete = Source.objects.filter(resource_id=self.resource_href) \
                                               .exclude(type_id__in=source_types).values('type_id')

        for source_type in source_types_to_delete:
            updates.append({
                'method': 'DELETE',
                'sourceType': source_type['type_id'],
                'resourceHref': self.resource_href,
            })

        changeset = self.get_new_changeset({'updates': updates,
                                            'description': 'PUT source list for {}'.format(self.resource_href)})
        changeset.perform()
        return HttpResponse(status=http.client.NO_CONTENT)

class SourceDetailView(VersioningMixin, ChangesetView):
    def get(self, request, resource_type, identifier, source_type, **kwargs):
        try:
            source = Source.objects.get(href=request.build_absolute_uri())
        except Source.DoesNotExist:
            resource_href = request.build_absolute_uri(reverse('halld:resource-detail', args=[resource_type,
                                                                                              identifier]))
            if not Resource.objects.filter(href=resource_href).count():
                raise exceptions.SourceDataWithoutResource(resource_href)
            raise exceptions.NoSuchSource(request.build_absolute_uri())
        if not request.user.has_perm('halld.view_source', source):
            raise exceptions.Forbidden(request.user)
        if self.check_version(source) is True:
            return HttpResponseNotModified()
        if source.deleted:
            raise exceptions.SourceDeleted
        data = source.get_hal(request.user)
        response = HttpResponse(json.dumps(data, indent=2, sort_keys=True),
                                content_type='application/hal+json')
        response['Last-Modified'] = wsgiref.handlers.format_date_time(mktime(source.modified.timetuple()))
        response['ETag'] = source.get_etag()
        return response

    def put(self, request, resource_type, identifier, source_type, **kwargs):
        hal = self.get_request_json('application/hal+json')
        try:
            data = get_halld_config().source_types[source_type].data_from_hal(hal)
        except KeyError:
            raise exceptions.NoSuchSourceType(source_type)

        changeset = self.get_new_changeset({'updates': [{'href': request.build_absolute_uri(),
                                                          'method': 'PUT',
                                                          'data': data}]})
        changeset.perform()
        return HttpResponse(status=http.client.NO_CONTENT)

    def patch(self, request, resource_type, identifier, source_type, **kwargs):
        patch = self.get_request_json('application/patch+json')
        changeset = self.get_new_changeset({'updates': [{'href': request.build_absolute_uri(),
                                                         'method': 'PATCH',
                                                         'patch': patch}]})
        changeset.perform()
        return HttpResponse(status=http.client.NO_CONTENT)

    @transaction.atomic
    def delete(self, request, resource_type, identifier, source_type, **kwargs):
        changeset = self.get_new_changeset({'updates': [{'href': request.build_absolute_uri(),
                                                         'method': 'DELETE'}]})
        changeset.perform()
        return HttpResponse(status=http.client.NO_CONTENT)

    @transaction.atomic
    def move(self, request, resource_type, identifier, source_type, **kwargs):
        raise NotImplementedError
