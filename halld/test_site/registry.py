import re

from halld.registry import ResourceTypeDefinition

class SnakeResourceTypeDefinition(ResourceTypeDefinition):
    name = 'snake'

    def get_inferences(self):
        return []

class PenguinResourceTypeDefinition(ResourceTypeDefinition):
    name = 'penguin'

    def user_can_assign_identifier(self, user, identifier):
        return user.is_superuser

    def get_inferences(self):
        return []

