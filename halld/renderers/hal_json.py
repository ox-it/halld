import copy
import json

from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse

from .base import HALLDRenderer
from .. import exceptions

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
        resource_type = resource_list['resource_type']

        paginator, page = self.get_paginator_and_page(resource_list['resources'])

        hal = copy.deepcopy(resource_type.get_type_properties())
        hal.update(self.paginated(paginator, page, self.resource_to_hal))
        hal['_links'].update({
            'find': {'href': reverse('halld:resource-list', args=[resource_type.name]) + '/{identifier}',
                     'templated': True},
            'findSource': {'href': reverse('halld:resource-list', args=[resource_type.name]) + '/{identifier}/source/{sourceType}',
                           'templated': True},
            'findSourceList': {'href': reverse('halld:resource-list', args=[resource_type.name]) + '/{identifier}/source',
                               'templated': True},
        })
        if resource_list['exclude_extant']:
            hal['_links']['includeExtant'] = {'href': self.url_param_replace(extant=None)}
        else:
            hal['_links']['excludeExtant'] = {'href': self.url_param_replace(extant='off')}
        if resource_list['exclude_defunct']:
            hal['_links']['includeDefunct'] = {'href': self.url_param_replace(defunct='on')}
        else:
            hal['_links']['excludeDefunct'] = {'href': self.url_param_replace(defunct=None)}
        return hal

    def render_resource(self, resource):
        return self.resource_to_hal(resource['resource'],
                                    include_links=True,
                                    include_source_links=True)
        

    def render_source_list(self, source_list):
        paginator, page = self.get_paginator_and_page(source_list['sources'])
        return self.paginated(paginator, page, self.source_to_hal)

    def render_source(self, source):
        return self.source_to_hal(source['source'])

    def resource_to_hal(self, resource, include_links=True, include_source_links=False):
        data = resource.get_filtered_data(self.user)

        hal = copy.deepcopy(data)
        hal['@extant'] = resource.extant
        links, embedded = {}, {}
        links['self'] = {'href': resource.href}

        if include_links and self.include_links:
            for link_type in self.halld_config.link_types.values():
                if not link_type.include:
                    continue
                for link_item in hal.pop(link_type.name, []):
                    if not link_item:
                        continue
                    try:
                        other_hal = self.resource_to_hal(self.object_cache.resource.get(link_item['href']), include_links=False)
                    except (exceptions.NoSuchResource, PermissionDenied):
                        continue
                    if link_type.embed:
                        link_item.update(other_hal)
                    elif 'title' in other_hal:
                        link_item['title'] = other_hal['title']

                    if link_type.timeless or (hal['@extant'] and other_hal['@extant']):
                        link_name = link_type.name
                        functional = link_type.functional
                    else:
                        link_name = 'defunct:' + link_type.name
                        functional = False

                    target = embedded if link_type.embed else links

                    if functional:
                        target[link_name] = link_item
                    else:
                        if link_name not in target:
                            target[link_name] = []
                        target[link_name].append(link_item)
        else:
            for link_type in self.halld_config.link_types.values():
                hal.pop(link_type.name, None)
        hal['_links'] = links
        if embedded:
            hal['_embedded'] = embedded
        
        if include_source_links:
            links['findSource'] = {'href': resource.href + '/source/{sourceName}',
                                   'templated': True}
            links['sourceList'] = {'href': resource.href + '/source'}

        hal['_meta'] = {'created': resource.created.isoformat(),
                        'modified': resource.modified.isoformat(),
                        'version': resource.version}
        return hal

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

    def paginated(self, paginator, page, to_hal_func):
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
            'item': list(map(to_hal_func, page.object_list))
        }
        return {
            '_links': links,
            '_embedded': embedded,
            'firstPage': 1,
            'lastPage': paginator.num_pages,
            'itemCount': paginator.count,
        }
