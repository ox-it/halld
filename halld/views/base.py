import copy
import json

from django.http import HttpResponse
from django_conneg.decorators import renderer
from django_conneg.views import ContentNegotiatedView
import rdflib
from rdflib_jsonld.parser import to_rdf as parse_jsonld

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
