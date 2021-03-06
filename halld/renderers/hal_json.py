import copy
import json

from django.core.urlresolvers import reverse

from .base import HALLDRenderer
from .. import exceptions
from .. import response_data

class HALJSONRenderer(HALLDRenderer):
    media_type = 'application/hal+json'
    format = 'hal-json'
    
    def serialize_data(self, data):
        return json.dumps(data, indent=2)
    
    def set_render_parameters(self, request):
        self.include_links = 'exclude_links' not in request.GET
        super().set_render_parameters(request)

    def render_index(self, index):
        return {'_links': index['links']}

    def render_resource_list(self, resource_list):
        hal = {}
        if 'resource_type' in resource_list:
            hal.update(resource_list['resource_type'].get_type_properties())

        paginator, page = resource_list['paginator'], resource_list['page']
        hal.update(self.paginated(paginator, page, self.resource_to_hal,
                                  resource_list.resource_data))

        if 'exclude_extant' in resource_list:
            if resource_list['exclude_extant']:
                hal['_links']['includeExtant'] = {'href': self.url_param_replace(extant=None)}
            else:
                hal['_links']['excludeExtant'] = {'href': self.url_param_replace(extant='off')}
        if 'exclude_defunct' in resource_list:
            if resource_list['exclude_defunct']:
                hal['_links']['includeDefunct'] = {'href': self.url_param_replace(defunct='on')}
            else:
                hal['_links']['excludeDefunct'] = {'href': self.url_param_replace(defunct=None)}
        return hal

    def render_resource(self, resource):
        return self.resource_to_hal(resource.data)
        

    def render_source_list(self, source_list):
        paginator, page = source_list['paginator'], source_list['page']
        return self.paginated(paginator, page, self.source_to_hal)

    def render_source(self, source):
        return self.source_to_hal(source['source'])

    def render_resource_type_list(self, resource_type_list):
        paginator, page = resource_type_list['paginator'], resource_type_list['page']
        return self.paginated(paginator, page, self.resource_type_to_hal)

    def render_resource_type(self, resource_type):
        return self.resource_type_to_hal(resource_type['resource_type'])

    def render_by_identifier(self, by_identifier):
        hal = {}
        for identifier, result in by_identifier['results'].items():
            if not result:
                hal[identifier] = None
                continue

            resource = response_data.Resource(resource=result['resource'],
                                              object_cache=by_identifier['object_cache'],
                                              user=by_identifier['user'],
                                              include_source_links=False)

            hal[identifier] = {'type': result['resource'].type_id,
                               'identifier': result['resource'].identifier,
                               'resourceHref': result['resource'].href}
            if 'sources' in result:
                hal[identifier]['sources'] = sources = {}
                for source_type, source in result['sources'].items():
                    if source:
                        sources[source_type] = self.source_to_hal(source)
                    else:
                        sources[source_type] = None
            if by_identifier.get('include_data'):
                hal[identifier]['data'] = self.resource_to_hal(resource.data)
        return hal

    def render_error(self, error):
        return dict(error)

    def resource_to_hal(self, data):
        links, embedded = {}, {}
        for link_type in self.halld_config.link_types.values():
            for prefix in ('', 'defunct:'):
                link_name = prefix + link_type.name
                link_items = data.pop(link_name, None)
                if not link_items:
                    continue
                if isinstance(link_items, dict):
                    link_items = self.resource_to_hal(link_items)
                elif isinstance(link_items, list):
                    link_items = list(map(self.resource_to_hal, link_items))
                if link_type.embed:
                    embedded[link_name] = link_items
                else:
                    links[link_name] = link_items
        for name in ('self', 'findSource', 'sourceList', 'describes'):
            if name in data:
                links[name] = data.pop(name)
        data['_links'] = links
        if embedded:
            data['_embedded'] = embedded
        return data

    def source_to_hal(self, source):
        data = copy.copy(source.data)
        data['_meta'] = {'version': source.version,
                         'sourceType': source.type_id,
                         'modified': source.modified.isoformat(),
                         'created': source.created.isoformat()}
        data['_links'] = {
            'self': {'href': source.href},
            'resource': {'href': source.resource_id},
        }
        return data

    def resource_type_to_hal(self, resource_type):
        data = resource_type.get_type_properties()
        return data

    def paginated(self, paginator, page, to_hal_func, objects=None):
        links = {
            'first': {'href': self.url_param_replace(page=1)},
            'last': {'href': self.url_param_replace(page=paginator.num_pages)},
            'page': {'href': self.url_param_replace(page='{page}'),
                     'templated': True},
        }
        if page.number > 1:
            links['previous'] = {'href': self.url_param_replace(page=page.number-1)}
        if page.number < paginator.num_pages:
            links['next'] = {'href': self.url_param_replace(page=page.number+1)}
        embedded = {
            'item': list(map(to_hal_func, objects or page.object_list))
        }
        return {
            '_links': links,
            '_embedded': embedded,
            'firstPage': 1,
            'lastPage': paginator.num_pages,
            'itemCount': paginator.count,
            'page': page.number,
        }
