import abc
import http.client

import jsonpointer

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

class NoSuchResource(HALLDException):
    name = 'no-such-resource'
    description = 'You are trying to update a source document for one or more resources that do not exist.'
    status_code = http.client.CONFLICT

    def __init__(self, hrefs):
        if not isinstance(hrefs, (list, tuple)):
            hrefs = (hrefs,)
        self.hrefs = hrefs

    def as_hal(self):
        hal = super(NoSuchResource, self).as_hal()
        hal['_links'] = {
            'missingResources': [{
                'href': href,
            } for href in self.hrefs],
        }
        return hal

class LinkTargetDoesNotExist(NoSuchResource):
    name = 'link-target-does-not-exist'
    description = 'The source data contains a link to a resource that does not exist.'

    def __init__(self, link_type, hrefs):
        super(LinkTargetDoesNotExist, self).__init__(hrefs)
        self.link_type = link_type

    def as_hal(self):
        hal = super(LinkTargetDoesNotExist, self).as_hal()
        hal['linkType'] = self.link_type.name
        return hal

class NoSuchSource(HALLDException):
    name = 'no-such-source'
    description = "You are attempting to view or update source data that doesn't yet exist. Create it with PUT first."
    status_code = http.client.NOT_FOUND

class IncompatibleSourceType(HALLDException):
    name = 'incompatible-source-type'
    description = "Sources of this type may not be attached to this type of resource"
    status_code = http.client.NOT_FOUND

    def __init__(self, resource_type, source_type):
        self.source_type, self.resource_type = source_type, resource_type

    def as_hal(self):
        hal = super(IncompatibleSourceType, self).as_hal()
        hal['resourceType'] = self.resource_type
        hal['sourceType'] = self.source_type
        return hal

class SourceValidationError(HALLDException):
    name = 'data-validation-failed'
    description = "The data you provided failed validation. Please consult the documentation for more details."
    status_code = http.client.BAD_REQUEST

class SchemaValidationError(SourceValidationError):
    name = 'schema-validation-failed'
    description = "The data you provided failed schema validation. Please consult the documentation for more details."
    status_code = http.client.BAD_REQUEST

    def __init__(self, e):
        self.message = e.message
        self.path = jsonpointer.JsonPointer.from_parts(e.path).path,
        self.schema_path = jsonpointer.JsonPointer.from_parts(e.schema_path).path

    def as_hal(self):
        hal = super(SourceValidationError, self).as_hal()
        if self.message is not None:
            hal['message'] = self.message
        if self.path is not None:
            hal['path'] = self.path
        if self.schema_path is not None:
            hal['schemaPath'] = self.schema_path
        return hal

class SourceDataWithoutResource(HALLDException):
    name = 'source-data-without-resource'
    description = 'You are attempting to view or update source data for a resource that does not exist. You should make sure the resource exists before trying again.'
    status_code = http.client.NOT_FOUND

    def __init__(self, hrefs):
        if isinstance(hrefs, str):
            hrefs = [hrefs]
        self.hrefs = hrefs

    def as_hal(self):
        hal = super(SourceDataWithoutResource, self).as_hal()
        hal['_links'] = {
            'missingResources': [{
                'href': href,
            } for href in self.hrefs],
        }
        return hal

class SourceValidationFailed(HALLDException):
    name = 'source-validation-failed'
    description = 'The source data you uploaded is invalid'

class NoSuchSourceType(HALLDException):
    name = 'no-such-source-type'
    description = 'There is no such source type'
    status_code = http.client.NOT_FOUND

    def __init__(self, source_type):
        self.source_type = source_type

    def as_hal(self):
        hal = super(NoSuchSourceType, self).as_hal()
        hal['sourceType'] = list(self.source_type)
        return hal

class NoSuchLinkType(HALLDException):
    name = 'no-such-link-type'
    description = 'There is no such link type'
    status_code = http.client.NOT_FOUND

    def __init__(self, link_type):
        self.link_type = link_type

    def as_hal(self):
        hal = super(NoSuchLinkType, self).as_hal()
        hal['linkType'] = list(self.link_type)
        return hal

class NoSuchIdentifier(HALLDException):
    name = 'no-such-identifier'
    description = 'There is no such identifier'
    status_code = http.client.NOT_FOUND

    def __init__(self, scheme, value):
        self.scheme, self.value = scheme, value

    def as_hal(self):
        hal = super(NoSuchIdentifier, self).as_hal()
        hal['scheme'] = self.scheme
        hal['value'] = self.value
        return hal

class DuplicatedIdentifier(HALLDException):
    name = 'duplicated-identifier'
    description = 'The data you supplied implied an identifier that is already assigned to another resource.'
    status_code = http.client.CONFLICT

    def __init__(self, scheme, value):
        self.scheme, self.value = scheme, value

    def as_hal(self):
        hal = super(DuplicatedIdentifier, self).as_hal()
        hal['scheme'] = self.scheme
        hal['value'] = self.value
        from .models import Identifier
        hal['_links'] = {'resource': Identifier.objects.get(scheme=self.scheme,
                                                            value=self.value).resource_id}
        return hal

class ResourceAlreadyExists(HALLDException):
    name = 'resource-already-exists'
    description = "You're trying to create a resource that already exists."
    status_code = http.client.CONFLICT
    
    def __init__(self, resource):
        self.resource = resource

class MissingContentType(HALLDException):
    name = 'missing-content-type'
    description = 'You must supply a Content-Type header.'
    status_code = http.client.BAD_REQUEST

class MissingContentLength(HALLDException):
    name = 'missing-content-length'
    description = 'You must supply a Content-Length header.'
    status_code = http.client.BAD_REQUEST

class UnsupportedContentType(HALLDException):
    name = 'unsupported-content-type'
    description = 'You supplied an unsupported Content-Type with your request.'
    status_code = http.client.BAD_REQUEST

class UnsupportedRequestBodyEncoding(HALLDException):
    name = 'unsupported-request-body-encoding'
    description = 'You specified an unsupported request body encoding. Try UTF-8 instead.'
    status_code = http.client.BAD_REQUEST

class InvalidJSON(HALLDException):
    name = 'invalid-json'
    description = "The request body you supplied wasn't valid JSON"
    status_code = http.client.BAD_REQUEST

class InvalidEncoding(HALLDException):
    name = 'invalid-encoding'
    description = "The request body you supplied couldn't be decoded using the expected character encoding."
    status_code = http.client.BAD_REQUEST

class InvalidParameter(HALLDException):
    name = 'invalid-parameter'
    description = "You supplied an invalid value for a query parameter."
    status_code = http.client.BAD_REQUEST

class MissingParameter(HALLDException):
    name = 'missing-parameter'
    description = "A required query parameter was missing."
    status_code = http.client.BAD_REQUEST

class CantReturnTree(HALLDException):
    name = 'cant-return-tree'
    description = "You requested a tree representation, but you specified more than one link, or that link is not inverse-functional"
    status_code = http.client.BAD_REQUEST

class MethodNotAllowed(HALLDException):
    name = 'method-not-allowed'
    description = 'The given HTTP method is not allowed'
    status_code = http.client.METHOD_NOT_ALLOWED

    def __init__(self, method, bad_request=False):
        self.method = method
        if bad_request:
            self.status_code = http.client.BAD_REQUEST

class Unauthorized(HALLDException):
    name = 'unauthorized'
    description = 'You need to authenticate to do that.'
    status_code = http.client.UNAUTHORIZED

class Forbidden(HALLDException):
    name = 'forbidden'
    description = 'You do not have permission to do that.'
    status_code = http.client.FORBIDDEN

    def __init__(self, user):
        if not request.user.is_authenticated:
            self.name = 'unauthorized'
            self.description = 'You need to authenticate to do that.'
            self.status_code = http.client.UNAUTHORIZED
