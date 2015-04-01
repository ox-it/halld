from lxml import etree
import PIL.Image

from halld.files.definitions import FileResourceTypeDefinition
from halld.files.exceptions import UnparsableFile
from halld.inference import FirstOf
from halld.definitions import ResourceTypeDefinition

class SnakeResourceTypeDefinition(ResourceTypeDefinition):
    name = 'snake'

    source_types = ['science', 'mythology']

    def get_inferences(self):
        return [
            FirstOf('', '/@source/science', update=True)
        ]

class PenguinResourceTypeDefinition(ResourceTypeDefinition):
    name = 'penguin'

    source_types = ['science', 'mythology']

    def user_can_assign_identifier(self, user, identifier):
        return user.is_superuser

image_content_types = {'image/jpeg', 'image/png'}

class DocumentResourceTypeDefinition(FileResourceTypeDefinition):
    name = 'document'

    source_types = ['file-metadata:image']

    def parse_file(self, f, content_type):
        if content_type in image_content_types:
            try:
                return PIL.Image.open(f)
            except OSError as e: # cannot identify image file
                raise UnparsableFile from e
        elif content_type == 'image/svg+xml':
            return etree.parse(f)
        else:
            return super().parse_file(f, content_type)

class URITemplatedResourceTypeDefinition(ResourceTypeDefinition):
    name = 'uri-templated'
    source_types = ['science']

    def get_uri_templates(self):
        return ['http://id.example.org/arbitrary/{foo}',
                'http://id.example.org/resource/{uri-templated}']
