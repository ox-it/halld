import cgi
import codecs
import copy
import datetime
import email.utils
import http.client
import json
from time import mktime
import wsgiref.handlers

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponsePermanentRedirect, HttpResponseNotModified, Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import View
from django_conneg.decorators import renderer
from django_conneg.http import HttpBadRequest, HttpResponseSeeOther, HttpError, HttpConflict, HttpGone, HttpResponseCreated
from django_conneg.views import ContentNegotiatedView, HTMLView, JSONView
import jsonpatch
import ujson
import rdflib
from rdflib_jsonld.parser import to_rdf as parse_jsonld

from . import exceptions
from .models import Resource, Source, Identifier
from halld.registry import get_resource_types, get_resource_type
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
            raise HttpError(http.client.BAD_REQUEST,
                            "You must supply a Content-type header of {}".format(media_type))
        if content_type != media_type:
            raise HttpError(http.client.UNSUPPORTED_MEDIA_TYPE,
                            "Content-type must be {0}.".format(media_type))
        charset = options.get('charset', 'utf-8')
        try:
            reader = codecs.getreader(charset)
        except LookupError:
            raise HttpError(http.client.BAD_REQUEST,
                            "Unsupported request body encoding.")
        try:
            return ujson.load(reader(self.request))
        except ValueError:
            raise HttpError(http.client.BAD_REQUEST,
                            "Couldn't parse JSON from request body.")
        except UnicodeDecodeError:
            raise HttpError(http.client.BAD_REQUEST,
                            "Request body not correctly encoded.")
        except LookupError:
            raise HttpError(http.client.BAD_REQUEST,
                            "Unsupported request body encoding.")

class HALLDView(ContentNegotiatedView):
    _default_format = 'hal'

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
        self.context.update({
            '@id': '',
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

    http_method_names = HALLDView.http_method_names + ['patch', 'link', 'unlink']

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

    def do_patch(self, request, source, patch):
        proposed = request.META.get('HTTP_X_PROPOSED') == 'yes' \
                or request.GET.get('proposed') == 'yes'
        
        if not patch:
            return HttpResponse(status=http.client.NO_CONTENT)

        if proposed:
            return self.make_patch_proposal(source, patch)

        if not request.user.has_perm('halld_source.change', source):
            raise PermissionDenied

        patched = jsonpatch.apply_patch(source.data, patch)
        if not source.patch_acceptable(request.user, patch):
            raise PermissionDenied
        filtered_patched = source.filter_data(request.user, patched)
        if patched != filtered_patched:
            raise PermissionDenied

        source.data = filtered_patched
        source.author = request.user
        source.committer = request.user
        source.save()
        return HttpResponse(status=http.client.NO_CONTENT)

class SourceListView(SourceView):
    @method_decorator(login_required)
    def dispatch(self, request, resource_type, identifier, **kwargs):
        print (resource_type)
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
        data = {source.type_id: source.filter_data(request.user) for source in visible_sources}
        response = HttpResponse(json.dumps(data, indent=2, sort_keys=True),
                                content_type='application/json')
        return response
    
    def put(self, request, resource_href, sources):
        sources = {source.type_id: source for source in sources}
        data = self.get_request_json('application/json')
        print(("DATA", data))
        if not isinstance(data, dict):
            raise HttpBadRequest
        for key in data:
            try:
                get_source_type(key)
            except KeyError:
                raise exceptions.NoSuchSourceType(key)

        for key in data:
            if key in sources:
                source = sources[key]
            else:
                resource = Resource.objects.get(href=resource_href)
                sources[key] = source = Source(resource=resource, type_id=key)

            old_data = source.filter_data(request.user)
            new_data = data[key]
            patch = jsonpatch.make_patch(old_data, new_data)
            self.do_patch(request, source, patch)
        return HttpResponse(status=http.client.NO_CONTENT)

class SourceDetailView(VersioningMixin, SourceView):
    @method_decorator(login_required)
    def dispatch(self, request, resource_type, identifier, source_type, **kwargs):
        try:
            resource_type = get_resource_type(resource_type)
        except KeyError:
            raise Http404
        try:
            source_type = get_source_type(source_type)
        except KeyError:
            raise exceptions.NoSuchSourceType(source_type)
        resource_href = resource_type.base_url + identifier
        source_href = resource_href + '/source/' + source_type.name
        try:
            source = Source.objects.get(href=source_href)
        except Source.DoesNotExist:
            try:
                resource = Resource.objects.get(href=resource_href)
            except Resource.DoesNotExist:
                raise exceptions.SourceDataWithoutResource(resource_type, identifier)
            if request.method.lower() in ('put', 'delete', 'patch', 'move'):
                source = Source(resource=resource, type_id=source_type.name)
            else:
                raise Http404

        return super(SourceDetailView, self).dispatch(request, source)

    def get(self, request, source):
        if not request.user.has_perm('halld.view_source', source):
            raise PermissionDenied
        if self.check_version(source) is True:
            return HttpResponseNotModified()
        if source.deleted:
            raise HttpGone
        data = source.filter_data(request.user)
        response = HttpResponse(json.dumps(data, indent=2, sort_keys=True),
                                content_type='application/json')
        response['Last-Modified'] = wsgiref.handlers.format_date_time(mktime(source.modified.timetuple()))
        response['ETag'] = source.get_etag()
        return response

    def put(self, request, source):
        if self.check_version(source) is False:
            raise HttpConflict
        data = self.get_request_json('application/json')
        old_data = source.filter_data(request.user)
        patch = jsonpatch.make_patch(old_data, data)
        return self.do_patch(request, source, patch)

    def patch(self, request, source):
        if self.check_version(source) is False:
            raise HttpConflict
        patch = self.get_request_json('application/patch+json')
        return self.do_patch(request, source, patch)

    def delete(self, request, resource, source_data):
        if not request.user.has_perm('halld.delete_sourcedata', source_data):
            raise PermissionDenied

        source_data.deleted = True
        source_data.author = request.user
        source_data.committer = request.user
        source_data.data = {}
        source_data.version += 1
        source_data.save()
        resource.regenerate()
        return HttpResponse(status_code=http.client.NO_CONTENT)

    def move(self, request, source_data):
        raise NotImplementedError
        if not request.user.has_perm('halld.move_sourcedata', source_data):
            raise PermissionDenied

        # TODO: Finish
        try:
            destination = request.META['HTTP_DESTINATION']
            destination = urlparse.urlparse(destination)
        except KeyError:
            raise HttpBadRequest

class IdView(View):
    def dispatch(self, request, resource_type, identifier):
        return HttpResponseSeeOther(reverse('resource', args=[resource_type, identifier]))

class ByIdentifierView(View):
    def get(self, request):
        try:
            scheme, value = request.GET['scheme'], request.GET['value']
        except KeyError:
            raise exceptions.MissingRequiredQueryParameters()
        try:
            identifier = Identifier.objects.get(scheme=scheme, value=value)
        except Identifier.DoesNotExist:
            raise exceptions.NoSuchIdentifier(scheme=scheme, value=value)