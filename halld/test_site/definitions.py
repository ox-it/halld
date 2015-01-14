from halld.files.definitions import FileResourceTypeDefinition
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

class DocumentResourceTypeDefinition(FileResourceTypeDefinition):
    name = 'document'

    source_types = ['file-metadata:image']

class URITemplatedResourceTypeDefinition(ResourceTypeDefinition):
    name = 'uri-templated'
    source_types = ['science']

    def get_uri_templates(self):
        return ['http://id.example.org/arbitrary/{foo}',
                'http://id.example.org/resource/{uri-templated}']
