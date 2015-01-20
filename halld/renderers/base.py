import abc

from django.core.paginator import Paginator
from django.http.request import QueryDict
from rest_framework.renderers import BaseRenderer

from .. import get_halld_config
from halld import response_data
from halld.util.cache import ObjectCache

class HALLDRenderer(BaseRenderer, metaclass=abc.ABCMeta):
    def render(self, data, media_type=None, renderer_context=None):
        self.set_render_parameters(renderer_context['request'])
        rendered_data = self.render_response_data(data)
        return self.serialize_data(rendered_data)

    response_data_types = {
        response_data.Index: 'render_index',
        response_data.ResourceList: 'render_resource_list',
        response_data.Resource: 'render_resource',
        response_data.SourceList: 'render_source_list',
        response_data.Source: 'render_source',
    }

    render_index = abc.abstractmethod(lambda index: None)
    render_resource_list = abc.abstractmethod(lambda resource_list: None)
    render_resource = abc.abstractmethod(lambda resource: None)
    render_source_list = abc.abstractmethod(lambda source_list: None)
    render_source = abc.abstractmethod(lambda source: None)

    def render_response_data(self, data):
        if not isinstance(data, response_data.ResponseData):
            raise TypeError("Can't render something of type %s; not a ResponseData" % type(data))
        for cls, method_name in self.response_data_types.items():
            if isinstance(data, cls):
                return getattr(self, method_name)(data)
        raise NotImplementedError("Can't render something of type %s; not a ResponseData" % type(data))

    def set_render_parameters(self, request):
        self.halld_config = get_halld_config()
        self.object_cache = getattr(request, 'object_cache') or ObjectCache()
        self.user = request.user
        self.request = request

    def get_paginator_and_page(self, objects):
        paginator = Paginator(objects, 100)
        try:
            page_num = int(self.request.GET.get('page'))
        except:
            page_num = 1
        return paginator, paginator.page(page_num)

    def url_param_replace(self, **kwargs):
        query = QueryDict(self.request.META['QUERY_STRING'], mutable=True)
        for key, value in kwargs.items():
            if not key:
                query.pop(key, None)
            else:
                query[key] = value
        if query:
            return self.request.path_info + '?' + query.urlencode('{}')
        else:
            return self.request.path_info

    @abc.abstractmethod
    def serialize_data(self, data):
        pass
