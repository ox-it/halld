from halld.apps import HALLDConfig

from halld.definitions import LinkTypeDefinition, SourceTypeDefinition
from halld.files.definitions import ImageMetadataSourceTypeDefinition

from . import definitions

class TestHALLDConfig(HALLDConfig):
    resource_type_classes = (
        definitions.DocumentResourceTypeDefinition,
        definitions.SnakeResourceTypeDefinition,
        definitions.PenguinResourceTypeDefinition,
        definitions.URITemplatedResourceTypeDefinition,
    )

    link_type_classes = (
        LinkTypeDefinition.new('eats', 'eatenBy'),
        LinkTypeDefinition.new('timelessF', 'timelessR', timeless=True),
        LinkTypeDefinition.new('functional', 'inverseFunctional', functional=True),
    )

    source_type_classes = (
        ImageMetadataSourceTypeDefinition,
        SourceTypeDefinition.new('science'),
        SourceTypeDefinition.new('mythology'),
        SourceTypeDefinition.new('conjecture'),
    )

