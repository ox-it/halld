import abc
import http.client

import jsonpointer
from rest_framework.exceptions import APIException

from . import response_data

class HALLDException(APIException, metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def name(self):
        pass

    def __init__(self):
        pass

    @property
    def detail(self):
        return response_data.Error({
            'error': self.name,
            'detail': self.description,
        })

class SourceDeleted(APIException):
    name = 'source-deleted'
    status_code = http.client.GONE

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

    @property
    def detail(self):
        data = super().detail
        data['resourceType'] = self.resource_type
        return data

class NotValidIdentifier(HALLDException):
    name = 'not-a-valid-identifier'
    description = 'The resource identifier is not valid'
    status_code = http.client.NOT_FOUND

    def __init__(self, identifier):
        self.identifier = identifier

    @property
    def detail(self):
        data = super().detail
        data['identifier'] = self.identifier
        return data

class NoSuchResource(HALLDException):
    name = 'no-such-resource'
    description = 'You are trying to update a source document for one or more resources that do not exist.'
    status_code = http.client.NOT_FOUND

    def __init__(self, hrefs):
        if not isinstance(hrefs, (list, tuple)):
            hrefs = (hrefs,)
        self.hrefs = hrefs

    @property
    def detail(self):
        data = super().detail
        data['_links'] = {
            'missingResources': [{
                'href': href,
            } for href in self.hrefs],
        }
        return data

class LinkTargetDoesNotExist(NoSuchResource):
    name = 'link-target-does-not-exist'
    description = 'The source data contains a link to a resource that does not exist.'

    def __init__(self, link_type, hrefs):
        super().__init__(hrefs)
        self.link_type = link_type

    @property
    def detail(self):
        data = super().detail
        data['linkType'] = self.link_type.name
        return data

class NoSuchSource(HALLDException):
    name = 'no-such-source'
    description = "You are attempting to view or update source data that doesn't yet exist. Create it with PUT first."
    status_code = http.client.NOT_FOUND

    def __init__(self, href):
        self.href = href

class IncompatibleSourceType(HALLDException):
    name = 'incompatible-source-type'
    description = "Sources of this type may not be attached to this type of resource"
    status_code = http.client.NOT_FOUND

    def __init__(self, resource_type, source_type):
        self.source_type, self.resource_type = source_type, resource_type

    @property
    def detail(self):
        data = super().detail
        data['resourceType'] = self.resource_type
        data['sourceType'] = self.source_type
        return data

class SourceValidationError(HALLDException):
    name = 'data-validation-failed'
    description = "The data you provided failed validation. Please consult the documentation for more descriptions."
    status_code = http.client.BAD_REQUEST

class SchemaValidationError(SourceValidationError):
    name = 'schema-validation-failed'
    description = "The data you provided failed schema validation. Please consult the documentation for more descriptions."
    status_code = http.client.BAD_REQUEST

    def __init__(self, e):
        self.__cause__ = e
        self.message = e.message
        self.path = jsonpointer.JsonPointer.from_parts(e.path).path,
        self.schema_path = jsonpointer.JsonPointer.from_parts(e.schema_path).path
        self.schema = e.schema

    @property
    def detail(self):
        data = super().detail
        if self.message is not None:
            data['message'] = self.message
        if self.path is not None:
            data['path'] = self.path
        if self.schema_path is not None:
            data['schemaPath'] = self.schema_path
        if self.schema is not None:
            data['schema'] = self.schema
        return data

class SourceDataWithoutResource(HALLDException):
    name = 'source-data-without-resource'
    description = 'You are attempting to view or update source data for a resource that does not exist. You should make sure the resource exists before trying again.'
    status_code = http.client.NOT_FOUND

    def __init__(self, hrefs):
        if isinstance(hrefs, str):
            hrefs = [hrefs]
        self.hrefs = hrefs

    @property
    def detail(self):
        data = super().detail
        data['_links'] = {
            'missingResources': [{
                'href': href,
            } for href in self.hrefs],
        }
        return data

class SourceValidationFailed(HALLDException):
    name = 'source-validation-failed'
    description = 'The source data you uploaded is invalid'

class NoSuchSourceType(HALLDException):
    name = 'no-such-source-type'
    description = 'There is no such source type'
    status_code = http.client.NOT_FOUND

    def __init__(self, source_type):
        self.source_type = source_type

    @property
    def detail(self):
        data = super().detail
        data['sourceType'] = list(self.source_type)
        return data

class NoSuchLinkType(HALLDException):
    name = 'no-such-link-type'
    description = 'There is no such link type'
    status_code = http.client.NOT_FOUND

    def __init__(self, link_type):
        self.link_type = link_type

    @property
    def detail(self):
        data = super().detail
        data['linkType'] = list(self.link_type)
        return data

class NoSuchIdentifier(HALLDException):
    name = 'no-such-identifier'
    description = 'There is no such identifier'
    status_code = http.client.NOT_FOUND

    def __init__(self, scheme, value):
        self.scheme, self.value = scheme, value

    @property
    def detail(self):
        data = super().detail
        data['scheme'] = self.scheme
        data['value'] = self.value
        return data

class DuplicatedIdentifier(HALLDException):
    name = 'duplicated-identifier'
    description = 'The data you supplied implied an identifier that is already assigned to another resource.'
    status_code = http.client.CONFLICT

    def __init__(self, scheme, value):
        self.scheme, self.value = scheme, value

    @property
    def detail(self):
        data = super().detail
        data['scheme'] = self.scheme
        data['value'] = self.value
        try:
            from .models import Identifier
            data['_links'] = {'resource': Identifier.objects.get(scheme=self.scheme,
                                                                value=self.value).resource_id}
        except Identifier.DoesNotExist:
            # User was likely uploading two things with the same identifier,
            # as opposed to there already being something we knew about with
            # the provided identifier. There's no way we're going to be able
            # to work out the resource href for the thing it clashed with.
            pass
        return data

class ResourceAlreadyExists(HALLDException):
    name = 'resource-already-exists'
    description = "You're trying to create a resource that already exists."
    status_code = http.client.CONFLICT

    def __init__(self, resource_type, identifier):
        self.resource_type = resource_type
        self.identifier = identifier

    @property
    def detail(self):
        data = super().detail
        data['resource_type'] = self.resource_type.name
        data['identifier'] = self.identifier
        return data

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

    def __init__(self, content_type, expected_content_type):
        self.content_type, self.expected_content_type = content_type, expected_content_type

    @property
    def detail(self):
        data = super().detail
        data['contentType'] = self.content_type
        data['expectedContentType'] = self.expected_content_type
        return data

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

    def __init__(self, parameter_name, parameter_detail=None):
        self.parameter_name, self.parameter_detail = parameter_name, parameter_detail

    @property
    def detail(self):
        data = super().detail
        data['parameterName'] = self.parameter_name
        if self.parameter_detail:
            data['parameterDetail'] = self.parameter_detail
        return data

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
        if not user.is_authenticated():
            self.name = 'unauthorized'
            self.description = 'You need to authenticate to do that.'
            self.status_code = http.client.UNAUTHORIZED

class MultipleErrors(HALLDException):
    name = 'multiple-errors'
    description = 'One or more errors occurred processing your request. See inside for more descriptions.'
    status_code = http.client.BAD_REQUEST

    def __init__(self, errors):
        self.errors = errors

    @property
    def detail(self):
        data = super().detail
        data['_embedded'] = {'error': [error.detail for error in self.errors]}
        return data

class CantRegenerateAll(HALLDException):
    name = 'cant-regenerate-all'
    description = 'You do not have the necessary privileges to regenerate all resources.'
    status_code = http.client.FORBIDDEN

