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

class CannotAssignIdentifier(HALLDException):
    name = 'cannot-assign-identifier'
    description = 'You are not permitted to assign identifiers for this type of resource. POST against the resource collection to have one assigned.'
    status_code = http.client.FORBIDDEN

class NoSuchResourceType(HALLDException):
    name = 'no-such-resource-type'
    description = 'There is no such resource type'
    status_code = http.client.NOT_FOUND

    def __init__(self, resource_type):
        self.resource_type = resource_type

    def as_hal(self):
        hal = super(NoSuchResourceType, self).as_hal()
        hal['resourceType'] = self.resource_type
        return hal

class NotValidIdentifier(HALLDException):
    name = 'not-a-valid-identifier'
    description = 'The resource identifier is not valid'
    status_code = http.client.NOT_FOUND

class LinkTargetDoesNotExist(HALLDException):
    name = 'link-target-does-not-exist'
    description = 'The source data contains a link to a resource that does not exist.'
    status_code = http.client.CONFLICT

    def __init__(self, link_type, href):
        self.link_type, self.href = link_type, href

    def as_hal(self):
        hal = super(LinkTargetDoesNotExist, self).as_hal()
        hal['_links'] = {
            'missingResource': {
                'href': self.href,
            },
        }
        hal['link_name'] = self.link_type.name
        return hal

class SourceDataWithoutResource(HALLDException):
    name = 'source-data-without-resource'
    description = 'You are attempting to view or update source data for a resource that does not exist. You should make sure the resource exists before trying again.'
    status_code = http.client.NOT_FOUND

    def __init__(self, resource_type, identifier):
        self.resource_type, self.identifier = resource_type, identifier

    def as_hal(self):
        hal = super(SourceDataWithoutResource, self).as_hal()
        hal['_links'] = {
            'missingResource': {
                'href': reverse('halld:resource', args=[self.resource_type.name, self.identifier]),
            },
        }
        return hal

class NoSuchSourceType(HALLDException):
    name = 'no-such-source-type'
    description = 'There is no such source type'
    status_code = http.client.NOT_FOUND

    def __init__(self, source_type):
        self.source_type = source_type

    def as_hal(self):
        hal = super(NoSuchSourceType, self).as_hal()
        hal['sourceType'] = self.source_type
        return hal

class ResourceAlreadyExists(HALLDException):
    name = 'resource-already-exists'
    description = "You're trying to create a resource that already exists."
    status_code = http.client.CONFLICT
    
    def __init__(self, resource):
        self.resource = resource