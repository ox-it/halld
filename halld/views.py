import cgi
import codecs
import copy
import datetime
import email.utils
import http.client
import urllib.parse
import json
import re
from time import mktime
import wsgiref.handlers

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponsePermanentRedirect, HttpResponseRedirect, HttpResponseNotModified, Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import View
from django_conneg.decorators import renderer
from django_conneg.http import HttpBadRequest, HttpResponseSeeOther, HttpError, HttpConflict, HttpGone, HttpResponseCreated
from django_conneg.views import ContentNegotiatedView, HTMLView, JSONView
import jsonpatch
import jsonschema
import ujson
import rdflib
from rdflib_jsonld.parser import to_rdf as parse_jsonld

from . import exceptions
from .models import Resource, Source, Identifier
from halld.registry import get_resource_types, get_resource_type, get_resource_types_by_href
from halld.registry import get_source_types, get_source_type
from .util.link_header import parse_link_value

def get_rdf_renderer(format, mimetype, name, rdflib_serializer):
    def render(self, request, context, template_name):
        hal = copy.deepcopy(self.context)
        jsonld = as_jsonld(hal)
        graph = rdflib.ConjunctiveGraph()
        parse_jsonld(jsonld, graph, request.build_absolute_uri())
        return HttpResponse(graph.serialize(format=rdflib_serializer),
                            mimetype=mimetype)
    render.__name__ = 'render_{}'.format(format)
    return renderer(format=format, mimetypes=(mimetype,), name=name)(render)

class VersioningMixin(View):
    def check_version(self, obj):
        etag = self.request.META.get('HTTP_IF_NONE_MATCH')
        if etag is not None:
            return etag == obj.get_etag()
        if_modified_since = self.request.META.get('HTTP_IF_MODIFIED_SINCE')
        if if_modified_since is not None:
            try:
                if_modified_since = datetime.datetime(*email.utils.parsedate(if_modified_since)[:6])
            except ValueError:
                raise HttpBadRequest
            return if_modified_since >= obj.modified

class JSONRequestMixin(View):
    def get_request_json(self, media_type='application/json'):
        try:
            content_type, options = cgi.parse_header(self.request.META['CONTENT_TYPE'])
        except KeyError:
            raise exceptions.MissingContentType()
        if content_type != media_type:
            raise exceptions.UnsupportedContentType()
        charset = options.get('charset', 'utf-8')
        try:
            reader = codecs.getreader(charset)
        except LookupError:
            raise exceptions.UnsupportedRequestBodyEncoding()
        try:
            return ujson.load(reader(self.request))
        except ValueError:
            raise exceptions.InvalidJSON()
        except UnicodeDecodeError:
            raise exceptions.InvalidEncoding()

class HALLDView(ContentNegotiatedView):
    _default_format = 'hal'
    _include_renderer_details_in_context = False

    @renderer(format='jsonld', mimetypes=('application/ld+json',), name='JSON-LD')
    def render_jsonld(self, request, context, template_name):
        self.context = as_jsonld(self.context)
        return HttpResponse(json.dumps(self.context, indent=2, sort_keys=True),
                            mimetype='application/ld+json')

    @renderer(format='hal', mimetypes=('application/hal+json',), name='HAL/JSON')
    def render_hal(self, request, context, template_name):
        return HttpResponse(json.dumps(self.context, indent=2, sort_keys=True),
                            mimetype='application/hal+json')

    render_rdf = get_rdf_renderer('rdf', 'application/rdf+xml', 'RDF/XML', 'pretty-xml')
    render_ttl = get_rdf_renderer('ttl', 'text/turtle', 'Turtle', 'turtle')
    render_nt = get_rdf_renderer('nt', 'text/plain', 'NTriples', 'nt')

class IndexView(HTMLView, HALLDView):
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

class ResourceTypeView(HALLDView):
    def dispatch(self, request, resource_type, **kwargs):
        try:
            resource_type = get_resource_type(resource_type)
        except KeyError:
            raise Http404
        return super(ResourceTypeView, self).dispatch(request, resource_type, **kwargs)

    def get(self, request, resource_type):
        paginator = Paginator(Resource.objects.filter(type_id=resource_type.name), 100)
        try:
            page_num = int(request.GET.get('page'))
        except:
            page_num = 1
        page = paginator.page(page_num)
        self.context.update(resource_type.get_type_properties())
        self.context.update({
            '@id': '',
            'id': resource_type.name,
            'label': resource_type.label,
            'labelPlural': resource_type.label_plural,
            '_links': {
                'first': {'href': '?page=1'},
                'last': {'href': '?page={0}'.format(paginator.num_pages)},
                'find': {'href': reverse('halld:resource-type', args=[resource_type.name]) + '/{identifier}',
                         'templated': True},
                'findSource': {'href': reverse('halld:resource-type', args=[resource_type.name]) + '/{identifier}/source/{source}',
                               'templated': True},
                'findSourceList': {'href': reverse('halld:resource-type', args=[resource_type.name]) + '/{identifier}/source',
                                   'templated': True},
            },
            '_embedded': {'item' :[resource.get_hal(request.user) for resource in page.object_list]},
        })
        if page_num > 1:
            self.context['_links']['previous'] = {'href': '?page={0}'.format(page_num - 1)}
        if page_num < paginator.num_pages:
            self.context['_links']['next'] = {'href': '?page={0}'.format(page_num + 1)}
        
        return self.render()

    def post(self, request, resource_type):
        identifier = resource_type.generate_identifier()
        resource = Resource.objects.create(type_id=resource_type.name,
                                           identifier=identifier)
        return HttpResponseCreated(resource.get_absolute_url())
        
class ResourceView(HALLDView):
    def dispatch(self, request, resource_type, identifier, **kwargs):
        try:
            resource_type = get_resource_type(resource_type)
        except KeyError:
            raise exceptions.NoSuchResourceType(resource_type)
        if not resource_type.is_valid_identifier(identifier):
            raise exceptions.NotValidIdentifier(identifier)
        href = resource_type.base_url + identifier
        return super(ResourceView, self).dispatch(request, resource_type, identifier, href, **kwargs)

    def get(self, request, resource_type, identifier, href):
        resource = get_object_or_404(Resource, href=href)
        self.context['resource'] = resource
        if resource.deleted:
            raise Http404
        elif not resource.extant:
            self.context['status_code'] = http.client.GONE
            
        #if resource.moved_to:
        #    return HttpResponsePermanentRedirect(resource.moved_to.get_absolute_url())
        return self.render()

    def post(self, request, resource_type, identifier, href):
        try:
            resource = Resource.objects.get(href=href)
        except Resource.DoesNotExist:
            if resource_type.user_can_assign_identifier(request.user, identifier):
                resource = Resource.objects.create(type_id=resource_type.name, identifier=identifier)
                return HttpResponseCreated(resource.get_absolute_url())
            else:
                raise exceptions.CannotAssignIdentifier
        else:
            raise exceptions.ResourceAlreadyExists(resource)

    @renderer(format='hal', mimetypes=('application/hal+json',), name='HAL/JSON')
    def render_hal(self, request, context, template_name):
        resource = context['resource']
        data = resource.filter_data(request.user, resource.data)
        hal = resource.get_hal(request.user, data)
        for source in resource.source_set.all():
            if not request.user.has_perm('halld.view_source', source):
                continue
            hal['_links']['source:{}'.format(source.type_id)] = {
                'href': source.get_absolute_url(),
            }
        hal['_links']['source'] = {
            'href': reverse('halld:source-list', args=[resource.type_id, resource.identifier]),
        }
        return HttpResponse(json.dumps(hal, indent=2, sort_keys=True),
                            mimetype='application/hal+json')

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
        pass

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

    def patch(self, request, source):
        if self.check_version(source) is False:
            raise HttpConflict
        patch = self.get_request_json('application/patch+json')
        self.do_patch(request, source, patch)
        return self.get(request, source)

    def delete(self, request, source):
        self.do_delete(request, source)
        return HttpResponse(status=http.client.NO_CONTENT)

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

class IdView(View):
    def dispatch(self, request, resource_type, identifier):
        return HttpResponseSeeOther(reverse('resource', args=[resource_type, identifier]))

class ByIdentifierView(JSONRequestMixin):
    schema = {
        'properties': {
            'scheme': {
                'type': 'string',
            },
            'values': {
                'type': 'array',
                'items': {'type': 'string'},
                'uniqueItems': True,
            },
            'includeData': {
                'type': 'boolean',
            },
            'includeSources': {
                'type': 'array',
                'items': {'type': 'string'},
                'uniqueItems': True,
            },
        },
        'required': ['scheme', 'values'],
    }
    def post(self, request):
        query = self.get_request_json()
        try:
            jsonschema.validate(query, self.schema)
        except jsonschema.ValidationError as e:
            raise exceptions.SchemaValidationError(e)
        identifiers = Identifier.objects.filter(scheme=query['scheme'],
                                                value__in=query['values']).select_related('resource')
        if query.get('includeSources'):
            identifiers = identifiers.select_related('resource__source_set')
        seen_values = set()
        results = {}
        for identifier in identifiers:
            resource = identifier.resource
            result = {'type': resource.type_id, 'identifier': resource.identifier}
            if query.get('includeData'):
                data = resource.filter_data(request.user, resource.data)
                result['data'] = resource.get_hal(request.user, data)
            if query.get('includeSources'):
                result['sources'] = {n: None for n in query['includeSources']}
                sources = resource.source_set.filter(type_id__in=query['includeSources'])
                for source in sources:
                    result['sources'][source.type_id] = source.get_hal(request.user)
            results[identifier.value] = result
            seen_values.add(identifier.value)
        for value in set(query['values']) - seen_values:
            results[value] = None
        return HttpResponse(json.dumps(results, indent=2), content_type='application/hal+json')