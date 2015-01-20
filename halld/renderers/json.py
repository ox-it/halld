import copy
import json

from rest_framework.renderers import BaseRenderer

class JSONRenderer(BaseRenderer):
    media_type = 'application/json'
    format = 'json'
    
    def render(self, data, media_type=None, renderer_context=None):
        if isinstance(data, (dict, list)):
            return json.dumps(data, indent=2)
        else:
            raise NotImplementedError
