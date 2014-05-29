from halld.files.registry import FileResourceTypeDefinition
from halld.inference import FirstOf
from halld.registry import ResourceTypeDefinition

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