import abc
import json
import itertools

from django.conf import settings
from django.http import HttpResponse, QueryDict
from django.views.generic.base import View
from rest_framework.views import APIView
import rest_framework.renderers
import rdflib
from rdflib_jsonld.parser import to_rdf as parse_jsonld

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

