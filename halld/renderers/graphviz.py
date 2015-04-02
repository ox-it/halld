import hashlib

try:
    import pydot
except ImportError:
    pydot = None

from rest_framework.renderers import BaseRenderer

__all__ = ['GraphVizRenderer']

class GraphVizRenderer(BaseRenderer):
    media_type = 'text/vnd.graphviz'
    format = 'gv'

    def serialize_data(self, data):
        return data.to_string()

    def render_resource_list(self, resource_list):
        def sha1(n):
            return hashlib.sha1(n.encode('utf-8')).hexdigest()
        
        graph, seen = pydot.Graph(), set()
        page = resource_list['page']
        for resource in page.object_list:
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
        return graph
