import json

from django.http import HttpResponse

from . import exceptions

class ExceptionMiddleware(object):
    def process_exception(self, request, exception):
        if isinstance(exception, exceptions.HALLDException):
            return HttpResponse(json.dumps(exception.as_hal(), indent=2),
                                content_type='application/hal+json',
                                status=exception.status_code)
