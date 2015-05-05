import http.client

from ..exceptions import HALLDException

class NotAFileResourceType(HALLDException):
    slug = 'not-a-file-resource-type'
    status_code = http.client.NOT_FOUND

class InvalidMultiPartFileCreation(HALLDException):
    slug = 'invalid-multipart-file-creation'
    status_code = http.client.BAD_REQUEST

class NoFileUploaded(HALLDException):
    slug = 'no-file-uploaded'
    status_code = http.client.BAD_REQUEST
    description = "A file upload was expected, but wasn't received."

class UnparsableFile(HALLDException):
    slug = 'unparsable-file'
    status_code = http.client.BAD_REQUEST
    description = "Couldn't parse uploaded file"

class Continue(HALLDException):
    slug = 'continue'
    status_code = http.client.CONTINUE
    description = "Go right ahead."
