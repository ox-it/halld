import http.client
import json
import re
from time import mktime
import urllib.parse
import wsgiref.handlers

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseNotModified
from django_conneg.http import HttpBadRequest, HttpGone, HttpConflict
from django_conneg.views import JSONView
import jsonpatch

from .mixins import JSONRequestMixin, VersioningMixin
from .. import exceptions
from ..models import Source, Resource
from ..registry import get_resource_types_by_href, get_resource_type, get_source_types, get_source_type

__all__ = ['SourceListView', 'SourceDetailView']

class SourceView(JSONView, JSONRequestMixin):
    source_href_re = re.compile(r'^(?P<source_href>(?P<resource_href>(?P<resource_type_href>.+)/(?P<identifier>[a-z\-\d]+))/source/(?P<source_type>[a-z\i\d:\-]+))$')
    def parse_source_href(self, href):
        match = self.source_href_re.match(href)
        if not match:
            raise ValueError
        return match.groupdict()

    def sources_for_hrefs(self, href_data, require_preexisting=True):
        sources = Source.objects.filter(href__in=set(href for href, data in href_data))
        sources = {source.href: source for source in sources}
        source_data = []

        resource_type_hrefs, source_types, bad_hrefs = set(), set(), set()
        parsed_href_data = []
        for href, data in href_data:
            try:
                parsed_href = self.parse_source_href(href)
            except ValueError:
                bad_hrefs.add(href)
            else:
                resource_type_hrefs.add(parsed_href['resource_type_href'])
                source_types.add(parsed_href['source_type'])
                parsed_href_data.append((parsed_href, data))
        if bad_hrefs:
            raise exceptions.BadHrefs(bad_hrefs)

        missing_resource_type_hrefs = resource_type_hrefs - set(get_resource_types_by_href())
        if missing_resource_type_hrefs:
            raise exceptions.NoSuchResourceType(missing_resource_type_hrefs)
        missing_source_types = source_types - set(get_source_types())
        if missing_source_types:
            raise exceptions.NoSuchSourceType(missing_source_types)

        # These hrefs don't necessarily exist, so we should check their
        # existence before we try to attach sources to them.
        missing_resource_hrefs = set()
        missing_source_hrefs = set()

        for parsed_href, data in parsed_href_data:
            try:
                source = sources[parsed_href['source_href']]
            except KeyError:
                missing_resource_hrefs.add(parsed_href['resource_href'])
                missing_source_hrefs.add(parsed_href['source_href'])
                source = Source(resource_id = parsed_href['resource_href'],
                                type_id=parsed_href['source_type'])
            source_data.append((source, data))

        if missing_resource_hrefs:
            found_resources = Resource.objects.filter(href__in=missing_resource_hrefs)
            found_resource_hrefs = {resource.href for resource in found_resources}
            missing_resource_hrefs -= found_resource_hrefs
            if missing_resource_hrefs:
                raise exceptions.SourceDataWithoutResource(missing_resource_hrefs)

        if require_preexisting and missing_source_hrefs:
            raise exceptions.NoSuchSource(missing_source_hrefs)

        return source_data

    def source_for_href(self, href, require_preexisting=True):
        source_data = self.sources_for_hrefs([(href, None)], require_preexisting)
        return source_data[0][0]

    def do_patch(self, request, source, patch):
        proposed = request.META.get('HTTP_X_PROPOSED') == 'yes' \
                or request.GET.get('proposed') == 'yes'

        # If there's no patch then there's nothing to be done unless
        # this is the first time this Source has been saved, or we're
        # resurrecting it (i.e. deleted is going from True to False)
        if not patch and source.pk and not source.deleted:
            return HttpResponse(status=http.client.NO_CONTENT)

        if proposed:
            return self.make_patch_proposal(source, patch)

        if source.pk and not request.user.has_perm('halld.change_source', source):
            raise PermissionDenied
        elif not source.pk and not request.user.has_perm('halld.add_source', source):
            raise PermissionDenied

        patched = jsonpatch.apply_patch(source.data, patch)
        if not source.patch_acceptable(request.user, patch):
            raise PermissionDenied
        source.validate_data(patched)
        filtered_patched = source.filter_data(request.user, patched)
        if patched != filtered_patched:
            raise PermissionDenied

        source.data = filtered_patched
        source.author = request.user
        source.committer = request.user
        source.deleted = False
        source.save()

    def do_delete(self, request, source):
        if not request.user.has_perm('halld.delete_source', source):
            raise PermissionDenied

        source.deleted = True
        source.author = request.user
        source.committer = request.user
        source.data = {}
        source.save()

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
        sources = Source.objects.filter(resource__href=resource_href)
        if not sources.count():
            try:
                Resource.objects.filter(href=resource_href).exists()
            except Resource.DoesNotExist:
                raise exceptions.SourceDataWithoutResource(resource_type, identifier)
        return super(SourceListView, self).dispatch(request, resource_href, sources)

    def get(self, request, resource_href, sources):
        visible_sources = [source for source in sources
                                  if not source.deleted and
                                     request.user.has_perm('halld.view_source', source)]
        embedded = {'source:{}'.format(source.type_id): source.get_hal(request.user) for source in visible_sources}
        data = {'_embedded': embedded}
        response = HttpResponse(json.dumps(data, indent=2, sort_keys=True),
                                content_type='application/hal+json')
        return response

    @transaction.atomic
    def put(self, request, resource_href, sources):
        data = self.get_request_json('application/hal+json')
        embedded = data.get('_embedded')
        if not isinstance(embedded, dict):
            raise HttpBadRequest
        
        source_data, missing_source_types = {}, set()
        for name in embedded:
            if not name.startswith('source:'):
                continue
            try:
                source_type = get_source_type(name[7:])
            except KeyError:
                missing_source_types.add(name[7:])
            else:
                source_data[source_type.name] = embedded[name]

        if missing_source_types:
            raise exceptions.NoSuchSourceType(missing_source_types)

        sources_by_type = {source.type_id: source for source in sources}
        for key in source_data:
            if key in sources:
                source = sources_by_type[key]
            else:
                resource = Resource.objects.get(href=resource_href)
                sources_by_type[key] = source = Source(resource=resource, type_id=key)

            if source_data[key] is None:
                self.do_delete(request, source)
            else:
                old_data = source.filter_data(request.user)
                new_data = source.data_from_hal(source_data[key])
                patch = jsonpatch.make_patch(old_data, new_data)
                self.do_patch(request, source, patch)
        return self.get(request, resource_href, sources)

class SourceDetailView(VersioningMixin, SourceView):
    @method_decorator(login_required)
    def dispatch(self, request, resource_type, identifier, source_type, **kwargs):
        require_preexisting = request.method.lower() not in {'put'}
        source = self.source_for_href(request.build_absolute_uri(),
                                      require_preexisting)

        source_types = get_resource_type(resource_type).source_types
        if source_types is not None and source_type not in source_types:
            raise exceptions.IncompatibleSourceType(resource_type, source_type)

        return super(SourceDetailView, self).dispatch(request, source)

    def get(self, request, source):
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
    def put(self, request, source):
        if self.check_version(source) is False:
            raise HttpConflict
        data = self.get_request_json('application/json')
        if data is None: # PUT null to delete a source
            return self.delete(request, source)
        if not isinstance(data, dict):
            raise exceptions.SourceValidationFailed
        old_data = source.filter_data(request.user)
        patch = jsonpatch.make_patch(old_data, data)
        self.do_patch(request, source, patch)
        return self.get(request, source)

    @transaction.atomic
    def patch(self, request, source):
        if self.check_version(source) is False:
            raise HttpConflict
        patch = self.get_request_json('application/patch+json')
        self.do_patch(request, source, patch)
        return self.get(request, source)

    @transaction.atomic
    def delete(self, request, source):
        self.do_delete(request, source)
        return HttpResponse(status=http.client.NO_CONTENT)

    @transaction.atomic
    def move(self, request, source_data):
        raise NotImplementedError
        if not request.user.has_perm('halld.move_source', source_data):
            raise PermissionDenied

        # TODO: Finish
        try:
            destination = request.META['HTTP_DESTINATION']
            destination = urllib.parse.urlparse(destination)
        except KeyError:
            raise HttpBadRequest
