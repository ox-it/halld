from lxml import etree
import PIL.Image

from halld.files.definitions import FileResourceTypeDefinition
from halld.files.definitions.parsers import PILFileParserMixin
from halld.inference import FirstOf
from halld.definitions import ResourceTypeDefinition

class SnakeResourceTypeDefinition(ResourceTypeDefinition):
    name = 'snake'

    source_types = ['science', 'mythology']

    def get_inferences(self):
        return [
            FirstOf('', '/@source/science', update=True),
            FirstOf('', '/@source/mythology', update=True),
        ]

class PenguinResourceTypeDefinition(ResourceTypeDefinition):
    name = 'penguin'

    source_types = ['science', 'mythology']

    def user_can_assign_identifier(self, user, identifier):
        return user.is_superuser

image_content_types = {'image/jpeg', 'image/png'}

class DocumentResourceTypeDefinition(PILFileParserMixin,
                                     FileResourceTypeDefinition):
    name = 'document'

    source_types = ['file-metadata:image']

class URITemplatedResourceTypeDefinition(ResourceTypeDefinition):
    name = 'uri-templated'
    source_types = ['science']

    def get_uri_templates(self):
        return ['http://id.example.org/arbitrary/{foo}',
                'http://id.example.org/resource/{uri-templated}']
