from halld.files.registry import FileResourceTypeDefinition
from halld.inference import FirstOf
from halld.registry import ResourceTypeDefinition

class SnakeResourceTypeDefinition(ResourceTypeDefinition):
    name = 'snake'

    def get_inferences(self):
        return [
            FirstOf('', '/@source/science', update=True)
        ]

class PenguinResourceTypeDefinition(ResourceTypeDefinition):
    name = 'penguin'

    def user_can_assign_identifier(self, user, identifier):
        return user.is_superuser

class DocumentResourceTypeDefinition(FileResourceTypeDefinition):
    name = 'document'