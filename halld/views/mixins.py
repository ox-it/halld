import cgi
import codecs
import datetime
import email.utils

from django.views.generic import View
import ujson

from .. import exceptions

class VersioningMixin(View):
    def check_version(self, obj):
        etag = self.request.META.get('HTTP_IF_NONE_MATCH')
        if etag is not None:
            return etag == obj.get_etag()
        if_modified_since = self.request.META.get('HTTP_IF_MODIFIED_SINCE')
        if if_modified_since is not None:
            try:
                if_modified_since = datetime.datetime(*email.utils.parsedate(if_modified_since)[:6])
            except ValueError:
                raise HttpBadRequest
            return if_modified_since >= obj.modified

class JSONRequestMixin(View):
    def get_request_json(self, expected_content_type='application/json'):
        try:
            content_type, options = cgi.parse_header(self.request.META['CONTENT_TYPE'])
        except KeyError:
            raise exceptions.MissingContentType()
        if content_type != expected_content_type:
            raise exceptions.UnsupportedContentType(content_type, expected_content_type)
        charset = options.get('charset', 'utf-8')
        try:
            reader = codecs.getreader(charset)
        except LookupError:
            raise exceptions.UnsupportedRequestBodyEncoding()
        try:
            return ujson.load(reader(self.request))
        except ValueError:
            raise exceptions.InvalidJSON()
        except UnicodeDecodeError:
            raise exceptions.InvalidEncoding()
