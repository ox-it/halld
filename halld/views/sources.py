import http.client
import json
from time import mktime
import wsgiref.handlers

from django.core.urlresolvers import reverse
from django.db import transaction
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseNotModified
from django_conneg.http import HttpBadRequest, HttpGone
from django_conneg.views import JSONView

from .mixins import VersioningMixin
from .. import exceptions, get_halld_config
from ..models import Source, Resource, Changeset
from .changeset import ChangesetView

__all__ = ['SourceListView', 'SourceDetailView']

class BulkSourceUpdateView(ChangesetView):
    @method_decorator(login_required)
    def post(self):
        raise NotImplementedError

class SourceListView(ChangesetView):
    def dispatch(self, request, resource_type, identifier, **kwargs):
        try:
            resource_type = get_halld_config().resource_types[resource_type]
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

        changeset = self.get_new_changeset({'updates': updates})
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
            raise HttpGone
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
