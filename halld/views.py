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

from .constants import RESOURCE_TYPE
from .context import jsonld_context
from . import exceptions
from .models import Resource, Source, SourceData
from .types import get_types
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
            'type:{}'.format(type.name): {
                'href': reverse('halld:resource-type', args=[type.name])}
            for type in get_types().values()
        }
        return self.render()

class ResourceTypeView(HALLDView):
    def dispatch(self, request, type, **kwargs):
        try:
            type = get_types()[type]
        except KeyError:
            raise Http404
        return super(ResourceTypeView, self).dispatch(request, type, **kwargs)

    def get(self, request, type):
        paginator = Paginator(Resource.objects.filter(type=type.name), 100)
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
                'find': {'href': reverse('halld:resource-type', args=[type.name]) + '/{identifier}',
                         'templated': True},
                'findSource': {'href': reverse('halld:resource-type', args=[type.name]) + '/{identifier}/source/{source}',
                               'templated': True},
            },
            '_embedded': {'item' :[resource.get_hal(request.user) for resource in page.object_list]},
        })
        if page_num > 1:
            self.context['_links']['previous'] = {'href': '?page={0}'.format(page_num - 1)}
        if page_num < paginator.num_pages:
            self.context['_links']['next'] = {'href': '?page={0}'.format(page_num + 1)}
        
        return self.render()

    def post(self, request, type):
        identifier = type.generate_identifier()
        resource = Resource.objects.create(type=type.name,
                                           identifier=identifier)
        return HttpResponseCreated(resource.get_absolute_url())
        
class ResourceView(HALLDView):

    http_method_names = HALLDView.http_method_names + ['patch', 'link', 'unlink']

    def dispatch(self, request, type, identifier, **kwargs):
        try:
            type = get_types()[type]
        except KeyError:
            raise Http404
        if not type.is_valid_identifier(identifier):
            raise Http404
        return super(ResourceView, self).dispatch(request, type, identifier, **kwargs)

    def get(self, request, type, identifier):
        resource = get_object_or_404(Resource, type=type.name, identifier=identifier)
        self.context['resource'] = resource
        if resource.deleted:
            raise Http404
        elif not resource.extant:
            self.context['status_code'] = http.client.GONE
            
        #if resource.moved_to:
        #    return HttpResponsePermanentRedirect(resource.moved_to.get_absolute_url())
        return self.render()

    def post(self, request, type, identifier):
        try:
            resource = Resource.objects.get(type=type.name, identifier=identifier)
        except Resource.DoesNotExist:
            if type.user_can_assign_identifier(request.user, identifier):
                resource = Resource.objects.create(type=type.name, identifier=identifier)
                return HttpResponseCreated(resource.get_absolute_url())
            else:
                raise PermissionDenied
        else:
            raise exceptions.ResourceAlreadyExists(resource)

    @renderer(format='hal', mimetypes=('application/hal+json',), name='HAL/JSON')
    def render_hal(self, request, context, template_name):
        resource = context['resource']
        data = resource.filter_data(request.user, resource.data)
        hal = resource.get_hal(request.user, data)
        for source_data in resource.sourcedata_set.all():
            if not request.user.has_perm('halld.view_source_data', source_data):
                continue
            hal['_links']['source:{}'.format(source_data.source_id)] = {
                'href': source_data.get_absolute_url(),
            }
        return HttpResponse(json.dumps(hal, indent=2, sort_keys=True),
                            mimetype='application/hal+json')


class SourceListView(JSONView):
    pass

class SourceDetailView(JSONView, VersioningMixin, JSONRequestMixin):
    @method_decorator(login_required)
    def dispatch(self, request, type, identifier, source):
        try:
            resource = Resource.objects.get(type=type, identifier=identifier)
        except Resource.DoesNotExist:
            raise exceptions.SourceDataWithoutResource(type, identifier)
        resource = get_object_or_404(Resource, type=type, identifier=identifier)
        try:
            source_data = SourceData.objects.get(resource=resource, source=source)
        except SourceData.DoesNotExist:
            source = get_object_or_404(Source, pk=source)
            if request.method.lower() in ('put', 'delete', 'patch', 'move'):
                source_data = SourceData(resource=resource, source=source)
            else:
                raise Http404
        
        return super(SourceDetailView, self).dispatch(request, resource, source_data)

    def get(self, request, resource, source_data):
        if not request.user.has_perm('halld.view_sourcedata', source_data):
            raise PermissionDenied
        if self.check_version(source_data) is True:
            return HttpResponseNotModified()
        if source_data.deleted:
            raise HttpGone
        data = source_data.filter_data(request.user)
        response = HttpResponse(json.dumps(data, indent=2, sort_keys=True),
                                content_type='application/json')
        response['Last-Modified'] = wsgiref.handlers.format_date_time(mktime(source_data.modified.timetuple()))
        response['ETag'] = source_data.get_etag()
        return response

    def put(self, request, resource, source_data):
        if self.check_version(source_data) is False:
            raise HttpConflict
        data = self.get_request_json('application/json')
        old_data = source_data.filter_data(request.user)
        patch = jsonpatch.make_patch(old_data, data)
        return self.do_patch(request, resource, source_data, patch)

    def patch(self, request, resource, source_data):
        if self.check_version(source_data) is False:
            raise HttpConflict
        patch = self.get_request_json('application/patch+json')
        return self.do_patch(request, resource, source_data, patch)

    def do_patch(self, request, resource, source_data, patch):
        proposed = request.META.get('HTTP_X_PROPOSED') == 'yes'
        
        if proposed:
            return self.make_patch_proposal(resource, source_data, patch)

        if not patch:
            pass#return HttpResponse(status=http.client.NO_CONTENT)
        
        if not request.user.has_perm('halld_sourcedata.change', source_data):
            raise PermissionDenied

        patched = jsonpatch.apply_patch(source_data.data, patch)
        if not source_data.patch_acceptable(request.user, patch):
            raise PermissionDenied
        filtered_patched = source_data.filter_data(request.user, patched)
        if patched != filtered_patched:
            raise PermissionDenied
        
        print("Applying")
        source_data.data = filtered_patched
        source_data.author = request.user
        source_data.committer = request.user
        source_data.version += 1
        source_data.save()
        resource.regenerate()
        return HttpResponse(status=http.client.NO_CONTENT)

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

    def move(self, request, resource, source_data):
        if not request.user.has_perm('halld.move_sourcedata', source_data):
            raise PermissionDenied

        # TODO: Finish
        try:
            destination = request.META['HTTP_DESTINATION']
            destination = urlparse.urlparse(destination)
        except KeyError:
            raise HttpBadRequest

class IdView(View):
    def dispatch(self, request, type, identifier):
        return HttpResponseSeeOther(reverse('resource', args=[type, identifier]))