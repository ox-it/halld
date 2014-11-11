import abc
import json
import itertools

from django.conf import settings
from django.http import HttpResponse, QueryDict
from django.views.generic.base import View
from django_conneg.decorators import renderer
from django_conneg.views import ContentNegotiatedView
import rdflib
from rdflib_jsonld.parser import to_rdf as parse_jsonld

from ..util.cache import ObjectCache

def get_rdf_renderer(format, content_type, name, rdflib_serializer):
    def render(self, request, context, template_name):
        jsonld = self.jsonld_from_context(context)
        graph = rdflib.ConjunctiveGraph()
        parse_jsonld(jsonld, graph, request.build_absolute_uri())
        return HttpResponse(graph.serialize(format=rdflib_serializer),
                            content_type=content_type)
    render.__name__ = 'render_{}'.format(format)
    return renderer(format=format, mimetypes=(content_type,), name=name)(render)

class ObjectCacheView(View):
    def dispatch(self, request, *args, **kwargs):
        self.object_cache = ObjectCache(request.user)
        return super(ObjectCacheView, self).dispatch(request, *args, **kwargs)

class HALLDView(ContentNegotiatedView, ObjectCacheView, metaclass=abc.ABCMeta):
    _default_format = 'hal'
    _include_renderer_details_in_context = False

    def url_param_replace(self, **kwargs):
        query = QueryDict(self.request.META['QUERY_STRING'], mutable=True)
        for key, value in kwargs.items():
            if not key:
                query.pop(key, None)
            else:
                query[key] = value
        if query:
            return self.request.path_info + '?' + query.urlencode('{}')
        else:
            return self.request.path_info

    @renderer(format='jsonld', mimetypes=('application/ld+json',), name='JSON-LD')
    def render_jsonld(self, request, context, template_name):
        jsonld = self.jsonld_from_context(request, context)
        return HttpResponse(json.dumps(self.context, indent=2, sort_keys=True),
                            content_type='application/ld+json')

    @renderer(format='hal', mimetypes=('application/hal+json',), name='HAL/JSON')
    def render_hal(self, request, context, template_name):
        hal_json = self.hal_json_from_context(request, context)
        return HttpResponse(json.dumps(hal_json, indent=2, sort_keys=True),
                            content_type='application/hal+json')

    @abc.abstractmethod
    def hal_json_from_context(self, request, context):
        return {}

    def jsonld_from_context(self, request, context):
        jsonld = self.hal_json_from_context(context)
        jsonld_context = self.get_jsonld_context()
        self.hal_resource_to_jsonld(jsonld, jsonld_context)
        jsonld['@context'] = jsonld_context
        return jsonld

    def hal_resource_to_jsonld(self, hal, jsonld_context):
        for subresources in itertools.chain(hal.get('_links', {}).values(),
                                            hal.get('_embedded', {}).values()):
            if not isinstance(subresources, list):
                subresources = [subresources]
            for subresource in subresources:
                self.hal_to_jsonld(subresource)
        if 'href' in hal and '@id' not in hal:
            hal['@id'] = hal.pop('href')
        hal.update(hal.pop('_links', {}))
        hal.update(hal.pop('_embedded', {}))
        for key in list(hal):
            if key not in jsonld_context:
                hal.pop(key)

    def get_jsonld_context(self):
        return getattr(settings, 'BASE_JSONLD_CONTEXT', {})

    render_rdf = get_rdf_renderer('rdf', 'application/rdf+xml', 'RDF/XML', 'pretty-xml')
    render_ttl = get_rdf_renderer('ttl', 'text/turtle', 'Turtle', 'turtle')
    render_nt = get_rdf_renderer('nt', 'text/plain', 'NTriples', 'nt')
