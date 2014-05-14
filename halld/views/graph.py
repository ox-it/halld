import hashlib
import json

from django.http import HttpResponse
from django_conneg.decorators import renderer

try:
    import pydot
except ImportError:
    pydot = None

from .base import HALLDView
from .. import exceptions
from ..models import Resource
from ..registry import get_link_type

__all__ = ['GraphView']

base_query = """
WITH RECURSIVE search_graph(href, type_id, data, depth, href_path, link_type_path, extant, link_extant, cycle) AS (
    SELECT r.href, r.type_id, r.data, 0,
        ARRAY[r.href::text],
        ARRAY[]::text[],
        r.extant,
        NULL::boolean,
        false
    FROM halld_resource r
    WHERE {initial_where_clause}
  UNION ALL
    SELECT r.href, r.type_id, r.data, sg.depth+1,
        (href_path || ARRAY[r.href::text]),
        (link_type_path || ARRAY[l.type_id]::text[]),
        r.extant,
        l.extant,
        r.href = ANY(href_path)
    FROM halld_resource r, halld_link l, search_graph sg
    WHERE l.passive_id = r.href AND l.active_id = sg.href AND NOT cycle AND {iterative_where_clause}
)
SELECT * FROM search_graph {limit_clause} {offset_clause}
"""



class GraphView(HALLDView):
    """
    Uses a `CTE <http://www.postgresql.org/docs/8.4/static/queries-with.html>`_
    to retrieve the transitive closure over a set of relations.
    """
    
    def get(self, request):
        roots = tuple(map(request.build_absolute_uri, request.GET.getlist('root')))
        links = tuple(request.GET.getlist('link'))
        types = tuple(request.GET.getlist('type'))
        start_types = tuple(request.GET.getlist('startType', types))
        include_unlinked = 'includeUnlinked' in request.GET
        return_tree = 'tree' in request.GET

        limit = self.get_integer_param(request, 'limit')
        offset = self.get_integer_param(request, 'offset')
        depth = self.get_integer_param(request, 'depth')

        if not links:
            raise exceptions.MissingParameter('link', 'You must supply one or more link names.')

        for link in links:
            try:
                link_type = get_link_type(link)
            except KeyError:
                raise exceptions.NoSuchLinkType(link)
        if return_tree and (len(links) > 1 or not link_type.inverse_functional):
            raise exceptions.CantReturnTree()

        initial_where_clause, initial_where_params = [], []
        iterative_where_clause, iterative_where_params = [], []
        
        if roots:
            initial_where_clause.append("r.href IN %s")
            initial_where_params.append(roots)
        else:
            initial_where_clause.append("NOT EXISTS (SELECT 1 FROM halld_link l WHERE l.passive_id = r.href AND l.type_id IN %s)")
            initial_where_params.append(links)
        if not include_unlinked:
            initial_where_clause.append("EXISTS (SELECT 1 FROM halld_link l WHERE l.active_id = r.href AND l.type_id IN %s)")
            initial_where_params.append(links)
        if start_types:
            initial_where_clause.append("r.type_id IN %s")
            initial_where_params.append(start_types)
        if depth:
            iterative_where_clause.append("sg.depth <= %s")
            iterative_where_params.append(depth)
        if types:
            iterative_where_clause.append("r.type_id IN %s")
            iterative_where_params.append(types)
        
        iterative_where_clause.append("l.type_id IN %s")
        iterative_where_params.append(links)
        
        params = initial_where_params + iterative_where_params
        
        if limit:
            limit_clause = 'LIMIT %s'
            params.append(limit)
        else:
            limit_clause = ''
        if offset:
            offset_clause = 'OFFSET %s'
            params.append(offset)
        else:
            offset_clause = ''

        query = base_query.format(initial_where_clause=' AND '.join(initial_where_clause),
                                  iterative_where_clause=' AND '.join(iterative_where_clause),
                                  limit_clause=limit_clause,
                                  offset_clause=offset_clause)

        resources = Resource.objects.raw(query, params)
        
        self.context.update({
            'resources': resources,
            'return_tree': return_tree,
        })
        return self.render()

    @renderer(format='hal', mimetypes=('application/hal+json',), name='HAL/JSON')
    def render_hal(self, request, context, template_name):
        links = {
            'root': [],
            'addLinkType': {'href': request.get_full_path() + '&link={linkType}',
                            'templated': True},
            'addRootResource': {'href': request.get_full_path() + '&root={href}',
                                'templated': True},
            'addStartTypeFilter': {'href': request.get_full_path() + '&startType={resourceType}',
                                    'templated': True},
            'addTypeFilter': {'href': request.get_full_path() + '&type={resourceType}',
                              'templated': True},
            'self': request.get_full_path(),
        }
        item_links = {}
        embedded_items = []
        hal = {
            '_links': links,
            '_embedded': {'item': embedded_items},
        }
        for resource in context['resources']:
            self_href = {'href': resource.href}
            data = resource.filter_data(request.user, resource.data)
            item = resource.get_hal(request.user, data, with_links=False)
            item_links[resource.href] = item['_links'] = {
                'self': self_href,
            }
            if resource.depth == 0:
                links['root'].append({'href': resource.href})
            else:
                if resource.link_type_path[-1] not in item_links[resource.href_path[-2]]:
                    item_links[resource.href_path[-2]][resource.link_type_path[-1]] = []
                item_links[resource.href_path[-2]][resource.link_type_path[-1]].append(self_href)
            embedded_items.append(item)
        return HttpResponse(json.dumps(hal, indent=2), content_type='application/hal+json')

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

    def get_integer_param(self, request, name):
        if name in request.GET:
            try:
                value = int(request.GET[name])
                if value < 0:
                    raise ValueError
                return value
            except ValueError:
                raise exceptions.InvalidParameter(name, 'Parameter must be a non-negative integer')
