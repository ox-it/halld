import collections
import hashlib
import json

from django.http import HttpResponse
from django_conneg.decorators import renderer
from rest_framework.response import Response
from halld import response_data

try:
    import pydot
except ImportError:
    pydot = None

from .base import HALLDView
from .. import exceptions
from ..models import Resource

__all__ = ['GraphView']

class GraphView(HALLDView):
    def get(self, request):
        roots = tuple(map(request.build_absolute_uri, request.GET.getlist('root')))
        links = set(request.GET.getlist('link'))
        links.discard('self')
        types = set(request.GET.getlist('type'))
        return_tree = 'tree' in request.GET
        exclude_extant = request.GET.get('extant', 'on') == 'off'
        exclude_defunct = request.GET.get('defunct', 'off') == 'off'

        limit = self.get_integer_param(request, 'limit')
        offset = self.get_integer_param(request, 'offset')
        depth = self.get_integer_param(request, 'depth', 10)

        if not roots:
            raise exceptions.MissingParameter('root', 'You must supply one or more root resource URLs.')
        if not links:
            raise exceptions.MissingParameter('link', 'You must supply one or more link names.')

        for link in links:
            try:
                link_type = self.halld_config.link_types[link]
            except KeyError:
                raise exceptions.NoSuchLinkType(link)
        if return_tree and (len(links) > 1 or not link_type.inverse_functional):
            raise exceptions.CantReturnTree()

        resources, seen, start = [], set(), set(roots)
        for i in range(depth):
            new_resources = request.object_cache.resource.get_many(start - seen)
            if types:
                new_resources = (r for r in new_resources if r.type_id in types)
            if not new_resources:
                break
            if exclude_extant:
                new_resources = (r for r in new_resources if not r.extant)
            if exclude_defunct:
                new_resources = (r for r in new_resources if r.extant)
            new_resources = list(new_resources)
            resources.extend(new_resources)
            seen.update(start)
            start = set()
            for resource in new_resources:
                resource.depth = i
                resource_data = resource.get_filtered_data(request.user)
                for link in links:
                    for rel in resource_data.get(link, ()):
                        start.add(rel['href'])

        paginator, page = self.get_paginator_and_page(resources)
        return Response(response_data.ResourceList(paginator=paginator,
                                                   page=page,
                                                   user=request.user,
                                                   object_cache=request.object_cache,
                                                   links=self.get_links(request)))

    def get_links(self, request):
        return {
            'addLinkType': {'href': request.get_full_path() + '&link={linkType}',
                            'templated': True},
            'addRootResource': {'href': request.get_full_path() + '&root={href}',
                                'templated': True},
            'addStartTypeFilter': {'href': request.get_full_path() + '&startType={resourceType}',
                                    'templated': True},
            'addTypeFilter': {'href': request.get_full_path() + '&type={resourceType}',
                              'templated': True},
        }

    if pydot:
        @renderer(format='gv', mimetypes=('text/vnd.graphviz',), name='GraphViz')
        def render_dot(self, request, context, template_name):
            def sha1(n):
                return hashlib.sha1(n.encode('utf-8')).hexdigest()

            graph, seen = pydot.Graph(), set()
            for resource in context['resources']:
                if resource.href not in seen:
                    node = pydot.Node(sha1(resource.href))
                    node.set_label(resource.data.get('title', ''))
                    if not resource.extant:
                        node.set_color('gray')
                        node.set_fontcolor('gray')
                    graph.add_node(node)
                    seen.add(resource.href)
                if resource.link_type_path:
                    edge_data = resource.href_path[-2], resource.link_type_path[-1], resource.href
                    if edge_data not in seen:
                        edge = pydot.Edge(sha1(resource.href_path[-2]), sha1(resource.href))
                        if not resource.link_extant:
                            edge.set_color('gray')
                        graph.add_edge(edge)
                        seen.add(edge_data)
            response = HttpResponse(graph.to_string(), content_type='text/vnd.graphviz')
            response['Content-Disposition'] = 'attachment; filename="graph.gv"'
            return response

    def get_integer_param(self, request, name, default=None):
        if name in request.GET:
            try:
                value = int(request.GET[name])
                if value < 0:
                    raise ValueError
                return value
            except ValueError:
                raise exceptions.InvalidParameter(name, 'Parameter must be a non-negative integer')
        else:
            return default
