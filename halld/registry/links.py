import abc
import importlib
import threading

class LinkTypeDefinition(object, metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def name(self):
        pass

    @abc.abstractproperty
    def inverse_name(self):
        pass

    functional = False
    inverse_functional = False
    include = True
    inverse_include = True
    embed = False
    inverse_embed = False
    subresource = False
    inverse_subresource = False
    inverted = False
    strict = True
    timeless = False

    @staticmethod
    def new(name, inverse_name,
            functional=False, inverse_functional=False,
            include=True, inverse_include=True,
            embed=False, inverse_embed=False,
            subresource=False, inverse_subresource=False,
            inverted=False, strict=True, timeless=False):
        link = type(name.title() + 'LinkTypeDefinition', (LinkTypeDefinition,),
                    {'name': name,
                     'inverse_name': inverse_name,
                     'functional': functional,
                     'inverse_functional': inverse_functional,
                     'include': include,
                     'inverse_include': inverse_include,
                     'embed': embed,
                     'inverse_embed': inverse_embed,
                     'subresource': subresource,
                     'inverse_subresource': inverse_subresource,
                     'inverted': inverted,
                     'strict': strict,
                     'timeless': timeless})
        return link()

    def inverse(self):
        return LinkTypeDefinition.new(self.inverse_name, self.name,
                                      self.inverse_functional, self.functional,
                                      self.inverse_include, self.include,
                                      self.inverse_embed, self.embed,
                                      self.inverse_subresource, self.subresource,
                                      not self.inverted, self.strict, self.timeless)

_local = threading.local()
def get_link_types():
    try:
        return _local.links
    except AttributeError:
        from django.conf import settings
        link_types = {}
        for link_type in settings.LINK_TYPES:
            if isinstance(link_type, str):
                mod_name, attr_name = link_types.rsplit('.', 1)
                link_type = getattr(importlib.import_module(mod_name), attr_name)()
            for link_type in [link_type, link_type.inverse()]:
                link_types[link_type.name] = link_type
        _local.links = link_types
        return link_types

def get_link_type(name):
    return get_link_types()[name]
