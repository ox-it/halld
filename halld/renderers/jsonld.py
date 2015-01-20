import json

from .base import HALLDRenderer

class JSONLDRenderer(HALLDRenderer):
    media_type = 'application/ld+json'
    format = 'jsonld'
    
    def serialize_data(self, data):
        data['@context'] = self.halld_config.jsonld_context
        return json.dumps(data, indent=2)

    def render_list(self, data):
        return {"item": map(self.render_data, data)}

    def render_index(self, index):
        return {}

    def render_resource_list(self, resource_list):
        return self.render_list(resource_list)

    def render_resource(self, resource):
        data = resource.get_filtered_data(self.user)
        return data

    def render_source_list(self, source_list):
        pass

    def render_source(self, source):
        pass
