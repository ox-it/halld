import abc

from django.core.paginator import Paginator
from rest_framework.views import APIView
import rest_framework.renderers

from ..util.cache import ObjectCache
import halld.renderers
from .. import get_halld_config

class HALLDView(APIView, metaclass=abc.ABCMeta):
    renderer_classes = (
        rest_framework.renderers.TemplateHTMLRenderer,
        halld.renderers.HALJSONRenderer,
        halld.renderers.JSONLDRenderer,
    )

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)

        request.object_cache = ObjectCache(request.user)
        self.halld_config = get_halld_config()


    def get_paginator_and_page(self, objects):
        paginator = Paginator(objects, 100)
        try:
            page_num = int(self.request.GET.get('page'))
        except:
            page_num = 1
        return paginator, paginator.page(page_num)
