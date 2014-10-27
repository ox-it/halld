import abc
from collections import defaultdict
import copy
import re
import threading
import urllib.parse
import uuid
import importlib

from .links import get_link_types
from .sources import get_source_type

uuid_re = re.compile('^[0-9a-f]{32}$')

class ResourceTypeDefinition(object, metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def name(self):
        pass

    @property
    def label(self):
        return self.name

    @property
    def label_plural(self):
        return self.label + 's'

    def get_type_properties(self):
        """
        Override to include additional properties in the type view.
        """
        return {}

    source_types = [] # Allow none by default

    @property
    def base_url(self):
        from django.conf import settings
        return '{}{}/'.format(settings.BASE_URL, self.name)

    @property
    def href(self):
        from django.conf import settings
        return '{}{}'.format(settings.BASE_URL, self.name)

    def get_inferences(self):
        inferences = []
        if self.source_types is not None:
            for source_type in self.source_types:
                source_type = get_source_type(source_type)
                inferences.extend(source_type.get_inferences())
        return inferences

    def get_normalizations(self):
        return [
            self.normalize_links,
            self.normalize_dates,
            self.add_inbound_links,
        ]

    def generate_identifier(self):
        return uuid.uuid4().hex

    def get_uri_templates(self):
        # None is special; it specifies a reverse on halld:id
        return [None]

    def get_identifiers(self, resource, data):
        return {}

    contributed_tags = frozenset()
    def get_contributed_tags(self, resource, data):
        return self.contributed_tags

    def get_hal(self, user, resource, data):
        hal = copy.deepcopy(data)
        links, embedded = {}, {}

        link_types = get_link_types()
        for link_type in link_types.values():
            link_items = hal.pop(link_type.name, None)
            if not link_items or not link_type.include:
                continue
            if link_type.functional:
                link_items = link_items[0]
            if link_type.embed:
                embedded[link_type.name] = link_items
            else:
                links[link_type.name] = link_items
        if links:
            hal['_links'] = links
        if embedded:
            hal['_embedded'] = embedded

        hal['_meta'] = {'created': resource.created.isoformat(),
                        'modified': resource.modified.isoformat(),
                        'version': resource.version}
        return hal

    def get_links(self, resource):
        from ..models import Link
        return Link.objects.filter(active=resource)

    allow_uri_override = False

    def is_valid_identifier(self, identifier):
        return uuid_re.match(identifier) is not None

    def user_can_assign_identifier(self, user, identifier):
        return False

    def user_can_create(self, user):
        from ..models import ResourceType
        return user.has_perm('halld.instantiate_resourcetype',
                             ResourceType.objects.get(name=self.name))

    def filter_data(self, user, resource, data):
        return data

    def normalize_links(self, resource, data):
        """
        Makes sure that each link is a list of dicts, each with a href.
        """
        for link_type in get_link_types().values():
            link_data = data.pop(link_type.name, None)
            if not link_data:
                continue
            links = []
            if not isinstance(link_data, list):
                link_data = [link_data]
            for link in link_data:
                if isinstance(link, str):
                    link = {'href': link}
                link['href'] = urllib.parse.urljoin(resource.href, link['href'])
                links.append(link)
            data[link_type.name] = links

    def normalize_dates(self, resource, data):
        pass # TODO

    def add_inbound_links(self, resource, data):
        pass

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
