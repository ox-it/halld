import abc
from collections import defaultdict
import copy
import re
import threading
import uuid
import importlib

from .links import get_links
from .permissions import VIEW_LINK

uuid_re = re.compile('^[0-9a-f]{32}$')

class Type(object, metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def name(self):
        pass

    @abc.abstractmethod
    def get_inferences(self):
        return []
    
    def generate_identifier(self):
        return uuid.uuid4().hex()

    def get_uri_templates(self):
        # None is special; it specifies a reverse on halld:id
        return [None]
    
    def get_hal(self, user, resource, data):
        hal = copy.deepcopy(data)
        links, embedded = defaultdict(list), defaultdict(list)

        link_types = get_links()
        for link in link_types.values():
            hal.pop(link.name, None)

        link_objs = self.get_links(user, resource, data)
        for link_obj in link_objs:
            if resource == link_obj.active:
                other = link_obj.passive
                link_type = link_types[link_obj.link_name]
            else:
                other = link_obj.active
                link_type = link_types[link_obj.link_name].inverse()
            if not link.include:
                continue
            add_to = embedded if link_type.embed else links
            if link_type.embed:
                other_data = other.get_hal(other.filter_data())
            else:
                other_data = {'href': other.get_absolute_url(),
                              '@id': other.uri}
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

    def get_links(self, user, resource, data):
        links = set(resource.link_active.all()) | set(resource.link_passive.all())
        links = set(l for l in links if user.has_perm(VIEW_LINK, l))
        return links
    
    allow_uri_override = False

    def is_valid_identifier(self, identifier):
        return uuid_re.match(identifier) is not None

    def user_can_assign_identifier(self, user, identifier):
        return False

_local = threading.local()
def get_types():
    try:
        return _local.types
    except AttributeError:
        from django.conf import settings
        types = {}
        for type in settings.TYPES:
            if isinstance(type, str):
                mod_name, attr_name = type.rsplit('.', 1)
                type = getattr(importlib.import_module(mod_name), attr_name)()
            types[type.name] = type
        _local.types = types
        return types
