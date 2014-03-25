import abc
from collections import defaultdict
import copy
import itertools
import re
import threading
import uuid
import importlib

from .links import get_link_types
from ..permissions import VIEW_LINK

uuid_re = re.compile('^[0-9a-f]{32}$')

class ResourceTypeDefinition(object, metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def name(self):
        pass
    
    @property
    def base_url(self):
        from django.conf import settings
        return '{}{}/'.format(settings.BASE_URL, self.name)

    @property
    def href(self):
        from django.conf import settings
        return '{}{}'.format(settings.BASE_URL, self.name)

    @abc.abstractmethod
    def get_inferences(self):
        from .. import inference
        return [
            inference.Identifiers(),
            inference.Types(),
        ]
    
    def generate_identifier(self):
        return uuid.uuid4().hex

    def get_uri_templates(self):
        # None is special; it specifies a reverse on halld:id
        return [None]

    def get_identifiers(self, resource, data):
        return {}

    contributed_types = frozenset()
    def get_contributed_types(self, resource, data):
        return self.contributed_types

    def get_hal(self, user, resource, data, with_links=True):
        hal = copy.deepcopy(data)
        links, embedded = defaultdict(list), defaultdict(list)

        link_types = get_link_types()
        for link_type in link_types.values():
            hal.pop(link_type.name, None)

        if with_links:
            for link in self.get_links(resource):
                if resource == link.active:
                    other = link.passive
                    link_type = link_types[link.type_id]
                else:
                    other = link.active
                    link_type = link_types[link.type_id].inverse()
                if not link_type.include:
                    continue
                add_to = embedded if link_type.embed and other else links
                if link_type.embed and other:
                    other_data = other.get_hal(other.filter_data(), with_links=False)
                elif other:
                    other_data = {'href': other.get_absolute_url(),
                                  '@id': other.get_absolute_uri()}
                else:
                    other_data = {'href': link.target_href}
                if link_type.functional:
                    add_to[link_type.name] = other_data
                else:
                    add_to[link_type.name].append(other_data)
            
            links['self'] = {'href': resource.get_absolute_url(),
                             '@id': resource.uri}
            hal['_links'] = dict(links)
            if embedded:
                hal['_embedded'] = dict(embedded)
        return hal
    
    def get_link_data(self, data):
        links = {n: data.get(n, ()) for n in get_link_types()}
        return links

    def get_links(self, resource):
        from ..models import Link
        from django.db.models import Q
        return Link.objects.filter(Q(source=resource) | Q(target=resource))

    allow_uri_override = False

    def is_valid_identifier(self, identifier):
        return uuid_re.match(identifier) is not None

    def user_can_assign_identifier(self, user, identifier):
        return False

    def filter_data(self, user, source, data):
        return data

class DefaultFilteredResourceTypeDefinition(ResourceTypeDefinition):
    """
    Subclass this to not expose any data by default.
    """
    def filter_data(self, user, source, data):
        return {}

_local = threading.local()
def get_resource_types():
    try:
        return _local.resource_types
    except AttributeError:
        from django.conf import settings
        resource_types, resource_types_by_href = {}, {}
        for resource_type in settings.RESOURCE_TYPES:
            if isinstance(resource_type, str):
                mod_name, attr_name = resource_type.rsplit('.', 1)
                resource_type = getattr(importlib.import_module(mod_name), attr_name)()
            resource_types[resource_type.name] = resource_type
            resource_types_by_href[resource_type.href] = resource_type
        _local.resource_types = resource_types
        _local.resource_types_by_href = resource_types_by_href
        return resource_types

def get_resource_type(name):
    return get_resource_types()[name]

def get_resource_types_by_href():
    get_resource_types()
    return _local.resource_types_by_href

def get_resource_type_by_href(href):
    get_resource_types()
    return _local.resource_types_by_href[href]
