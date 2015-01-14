from django.db.models.signals import post_syncdb

import halld.models
from halld import get_halld_config

def register_type_definitions(sender, **kwargs):
    """
    Adds records to the ResourceType, LinkType, SourceType models
    from the definitions in the halld.definitions.
    """
    for link_type in get_halld_config().link_types.values():
        halld.models.LinkType.objects.get_or_create(name=link_type.name)
    for resource_type in get_halld_config().resource_types.values():
        halld.models.ResourceType.objects.get_or_create(name=resource_type.name)
    for source_type in get_halld_config().source_types.values():
        halld.models.SourceType.objects.get_or_create(name=source_type.name)

post_syncdb.connect(register_type_definitions, sender=halld.models)
