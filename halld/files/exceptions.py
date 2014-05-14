import http.client

from ..exceptions import HALLDException

class NotAFileResourceType(HALLDException):
    slug = 'not-a-file-resource-type'
    status_code = http.client.NOT_FOUND
