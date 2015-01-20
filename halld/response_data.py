class ResponseData(object):
    pass

class Index(ResponseData):
    def __init__(self, links):
        self.links = links

class ResourceList(ResponseData):
    def __init__(self, resources, resource_type=None, exclude_extant=False, exclude_defunct=True):
        self.resources = resources
        self.resource_type = resource_type
        self.exclude_extant = exclude_extant
        self.exclude_defunct = exclude_defunct

class Resource(ResponseData):
    def __init__(self, resource):
        self.resource = resource

class SourceList(ResponseData):
    def __init__(self, sources):
        self.sources = sources

class Source(ResponseData):
    def __init__(self, source):
        self.source = source
