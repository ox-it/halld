import threading

class Link(object):
    def __init__(self, name, inverse_name,
                 functional=False, inverse_functional=False,
                 include=True, inverse_include=True,
                 embed=False, inverse_embed=False,
                 subresource=False, inverse_subresource=False,
                 inverted=False):
        self.name, self.inverse_name = name, inverse_name
        self.functional, self.inverse_functional = functional, inverse_functional
        self.include, self.inverse_include = include, inverse_include
        self.embed, self.inverse_embed = embed, inverse_embed
        self.subresource, self.inverse_subresource = subresource, inverse_subresource
        self.inverted = inverted

    def inverse(self):
        return Link(self.inverse_name, self.name,
                    self.inverse_functional, self.functional,
                    self.inverse_include, self.include,
                    self.inverse_embed, self.embed,
                    self.inverse_subresource, self.subresource,
                    not self.inverted)

_local = threading.local()
def get_links():
    try:
        return _local.links
    except AttributeError:
        from django.conf import settings
        links = {}
        for link in settings.LINKS:
            for link in [link, link.inverse()]:
                links[link.name] = link
        _local.links = links
        return links
