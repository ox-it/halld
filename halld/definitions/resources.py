import abc
import copy
import re
import threading
import urllib.parse
import uuid
import importlib

from django.apps import apps
from django.core.exceptions import PermissionDenied

from .. import get_halld_config
from .. import exceptions

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
                source_type = get_halld_config().source_types[source_type]
                inferences.extend(source_type.get_inferences())
        return inferences

    def get_normalizations(self):
        return [
            self.normalize_links,
            self.add_inbound_links,
            self.sort_links,
            self.normalize_dates,
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

    def get_hal(self, user, resource, object_cache, data, exclude_links=False):
        hal = copy.deepcopy(data)
        hal['@extant'] = resource.extant
        links, embedded = {}, {}
        links['self'] = {'href': resource.href}

        if not exclude_links:
            app_config = get_halld_config()
            for link_type in app_config.link_types.values():
                if not link_type.include:
                    continue
                for link_item in hal.pop(link_type.name, []):
                    if not link_item:
                        continue
                    try:
                        other_hal = object_cache.resource.get_hal(link_item['href'], exclude_links=True)
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

    def get_filtered_data(self, user, resource, data):
        return data

    def normalize_links(self, resource, data, **kwargs):
        """
        Makes sure that each link is a list of dicts, each with a href.
        """
        for link_type in get_halld_config().link_types.values():
            link_data = data.pop(link_type.name, None)
            if not link_data:
                continue
            links = []
            if not isinstance(link_data, list):
                link_data = [link_data]
            for link in link_data:
                if link is None:
                    continue
                if isinstance(link, str):
                    link = {'href': link}
                link['href'] = urllib.parse.urljoin(resource.href, link['href'])
                links.append(link)
            if links:
                data[link_type.name] = links

    def normalize_dates(self, resource, data, **kwargs):
        pass # TODO

    def add_inbound_links(self, resource, data, **kwargs):
        from ..models import Link
        for link in Link.objects.filter(target_href=resource.href):
            link_type = get_halld_config().link_types[link.type_id].inverse()
            link_dict = {'href': link.source_id,
                         'inbound': True}
            if link_type.name in data:
                data[link_type.name].append(link_dict)
            else:
                data[link_type.name] = [link_dict]

    def sort_links(self, resource, data, **kwargs):
        for link_type in get_halld_config().link_types.values():
            try:
                links = data[link_type.name]
            except KeyError:
                continue
            else:
                links.sort(key=lambda link: link['href'])

class DefaultFilteredResourceTypeDefinition(ResourceTypeDefinition):
    """
    Subclass this to not expose any data by default.
    """
    def filter_data(self, user, source, data):
        return {}

