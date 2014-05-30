import http.client
import json
import re
from time import mktime
import urllib.parse
import wsgiref.handlers

from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db import transaction
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseNotModified
from django.shortcuts import get_object_or_404
from django_conneg.http import HttpBadRequest, HttpGone, HttpConflict
from django_conneg.views import JSONView
import jsonpatch

from .mixins import JSONRequestMixin, VersioningMixin
from .. import exceptions
from ..models import Source, Resource
from ..registry import get_resource_types_by_href, get_resource_type, get_source_types, get_source_type
from ..update_source import SourceUpdater

__all__ = ['SourceListView', 'SourceDetailView']

class SourceView(JSONView, JSONRequestMixin):
    def dispatch(self, request, *args, **kwargs):
        self.source_updater = SourceUpdater(request.build_absolute_uri(),
                                            request.user)
        return JSONView.dispatch(self, request, *args, **kwargs)

class BulkSourceUpdateView(SourceView):
    @method_decorator(login_required)
    def post(self):
        raise NotImplementedError

class SourceListView(SourceView):
    @method_decorator(login_required)
    def dispatch(self, request, resource_type, identifier, **kwargs):
        try:
            resource_type = get_resource_type(resource_type)
        except KeyError:
            raise exceptions.NoSuchResourceType(resource_type)
        resource_href = resource_type.base_url + identifier
        if not Resource.objects.filter(href=resource_href).exists():
            raise exceptions.SourceDataWithoutResource(resource_type, identifier)
        return super(SourceListView, self).dispatch(request, resource_href)

    def get(self, request, resource_href):
        sources = Source.objects.filter(resource_id=resource_href)
        visible_sources = [source for source in sources
                                  if not source.deleted and
                                     request.user.has_perm('halld.view_source', source)]
        embedded = {'source:{}'.format(source.type_id): source.get_hal(request.user) for source in visible_sources}
        data = {'_embedded': embedded}
        response = HttpResponse(json.dumps(data, indent=2, sort_keys=True),
                                content_type='application/hal+json')
        return response

    @transaction.atomic
    def put(self, request, resource_href):
        data = self.get_request_json('application/hal+json')
        embedded = data.get('_embedded')
        if not isinstance(embedded, dict):
            raise HttpBadRequest
        
        updates = []
        for name in embedded:
            if not name.startswith('source:'):
                continue
            source_type = name[7:]
            updates.append({
                'method': 'PUT',
                'sourceType': source_type,
                'resourceHref': resource_href,
                'data': embedded[name],
            })

        self.source_updater.perform_updates({'updates': updates})
        return HttpResponse(status=http.client.NO_CONTENT)

class SourceDetailView(VersioningMixin, SourceView):
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
            raise PermissionDenied
        if self.check_version(source) is True:
            return HttpResponseNotModified()
        if source.deleted:
            raise HttpGone
        data = source.get_hal(request.user)
        response = HttpResponse(json.dumps(data, indent=2, sort_keys=True),
                                content_type='application/hal+json')
        response['Last-Modified'] = wsgiref.handlers.format_date_time(mktime(source.modified.timetuple()))
        response['ETag'] = source.get_etag()
        return response

    @transaction.atomic
    def put(self, request, resource_type, identifier, source_type, **kwargs):
        hal = self.get_request_json('application/hal+json')
        data = get_source_type(source_type).data_from_hal(hal)
        self.source_updater.perform_updates({'updates': [{'href': request.build_absolute_uri(),
                                                          'method': 'PUT',
                                                          'data': data}]})
        return HttpResponse(status=http.client.NO_CONTENT)

    @transaction.atomic
    def patch(self, request, resource_type, identifier, source_type, **kwargs):
        patch = self.get_request_json('application/patch+json')
        self.source_updater.perform_updates({'updates': [{'href': request.build_absolute_uri(),
                                                          'method': 'PATCH',
                                                          'patch': patch}]})
        return HttpResponse(status=http.client.NO_CONTENT)

    @transaction.atomic
    def delete(self, request, resource_type, identifier, source_type, **kwargs):
        self.source_updater.perform_updates({'updates': [{'href': request.build_absolute_uri(),
                                                          'method': 'DELETE'}]})
        return HttpResponse(status=http.client.NO_CONTENT)


    @transaction.atomic
    def move(self, request, resource_type, identifier, source_type, **kwargs):
        raise NotImplementedError
        if not request.user.has_perm('halld.move_source', source_data):
            raise PermissionDenied

        # TODO: Finish
        try:
            destination = request.META['HTTP_DESTINATION']
            destination = urllib.parse.urlparse(destination)
        except KeyError:
            raise HttpBadRequest
