from django.core.exceptions import PermissionDenied
from django.utils.functional import cached_property

from halld import get_halld_config
from django.core.urlresolvers import reverse

class ResponseData(dict):
    property_keys = set()

    def __init__(self, *args, **kwargs):
        self.halld_config = get_halld_config()
        super().__init__(*args, **kwargs)

    def __contains__(self, key, *args, **kwargs):
        if key in self.property_keys:
            return True
        return dict.__contains__(self, key, *args, **kwargs)

    def __getitem__(self, key, *args, **kwargs):
        if key in self.property_keys:
            return getattr(self, key)
        return dict.__getitem__(self, key, *args, **kwargs)

class Index(ResponseData):
    pass

class ResourceList(ResponseData):
    property_keys = {'resource_data'}

    @cached_property
    def resource_data(self):
        return (Resource(resource=resource,
                         object_cache=self['object_cache'],
                         include_source_links=False,
                         user=self['user']).data for resource in self['page'].object_list)

class Resource(ResponseData):
    property_keys = {'data'}

    @cached_property
    def data(self):
        from . import exceptions
        from halld.files.models import ResourceFile
        from halld.files.definitions.resources import FileResourceTypeDefinition
        data = self['resource'].get_filtered_data(self['user'])

        data['_extant'] = self['resource'].extant
        data['self'] = {'href': self['resource'].href}

        link_names = set()
        if self.get('include_links', True):
            for link_type in self.halld_config.link_types.values():
                link_items = data.pop(link_type.name, [])
                if not link_type.include:
                    continue
                for link_item in link_items:
                    if not link_item:
                        continue
                    try:
                        other_resource = self.copy()
                        other_resource.update(resource=self['object_cache'].resource.get(link_item['href']),
                                              include_links=False,
                                              include_source_links=False)
                        other_data = Resource(other_resource).data
                    except (exceptions.NoSuchResource, PermissionDenied):
                        continue
                    if link_type.embed:
                        link_item.update(other_data)
                    elif 'title' in other_data:
                        link_item['title'] = other_data['title']

                    if link_type.timeless or (data['_extant'] and other_data['_extant']):
                        link_name = link_type.name
                        functional = link_type.functional
                    else:
                        link_name = 'defunct:' + link_type.name
                        functional = False

                    if functional:
                        data[link_name] = link_item
                    else:
                        if link_name not in data:
                            data[link_name] = []
                        data[link_name].append(link_item)
                    link_names.add(link_name)
            for link_name in link_names:
                if isinstance(data.get(link_name), list):
                    data[link_name].sort(key=lambda link: link.get('title'))
        else:
            for link_type in self.halld_config.link_types.values():
                data.pop(link_type.name, None)

        if isinstance(self['resource'].get_type(), FileResourceTypeDefinition):
            data['describes'] = {
                'href': reverse('halld-files:file-detail',
                                args=[self['resource'].type_id,
                                      self['resource'].identifier]),
                'type': ResourceFile.objects.get(resource=self['resource']).content_type,
            }

        if self.get('include_source_links', True):
            data['findSource'] = {'href': self['resource'].href + '/source/{sourceName}',
                                   'templated': True}
            data['sourceList'] = {'href': self['resource'].href + '/source'}

        data['_meta'] = {'created': self['resource'].created.isoformat(),
                        'modified': self['resource'].modified.isoformat(),
                        'version': self['resource'].version}
        return data

class SourceList(ResponseData):
    pass

class Source(ResponseData):
    pass

class ResourceTypeList(ResponseData):
    pass

class ResourceType(ResponseData):
    pass

class Error(ResponseData):
    pass