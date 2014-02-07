import abc
import http.client

from django.core.urlresolvers import reverse

class HALLDException(Exception, metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def name(self):
        pass

    @abc.abstractproperty
    def description(self):
        pass

    @abc.abstractproperty
    def status_code(self):
        pass

    def as_hal(self):
        return {
            'error': self.name,
            'description': self.description,
        }

class LinkTargetDoesNotExist(HALLDException):
    name = 'link-target-does-not-exist'
    description = 'The source data contains a link to a resource that does not exist.'

    def __init__(self, link, rid):
        self.link, self.rid = link, rid

    def as_hal(self):
        hal = super(LinkTargetDoesNotExist, self).as_hal()
        hal['_links'] = {
            'missingResource': {
                'href': reverse('halld:index') + self.rid,
            },
        }
        hal['link_name'] = self.link.name
        return hal

class SourceDataWithoutResource(HALLDException):
    name = 'source-data-without-resource'
    description = 'You are attempting to view or update source data for a resource that does not exist. You should make sure the resource exists before trying again.'
    status_code = http.client.NOT_FOUND

    def __init__(self, type, identifier):
        self.type, self.identifier = type, identifier

    def as_hal(self):
        hal = super(SourceDataWithoutResource, self).as_hal()
        hal['_links'] = {
            'missingResource': {
                'href': reverse('halld:resource', args=[self.type, self.identifier]),
            },
        }
        return hal

class ResourceAlreadyExists(HALLDException):
    name = 'resource-already-exists'
    description = "You're trying to create a resource that already exists."
    status_code = http.client.CONFLICT
    
    def __init__(self, resource):
        self.resource = resource