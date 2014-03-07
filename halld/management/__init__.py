from django.db.models.signals import post_syncdb

import halld.models
from halld.registry import get_link_types, get_resource_types, get_source_types

def register_registry_types(sender, **kwargs):
    """
    Adds records to the ResourceType, LinkType, SourceType models
    from the definitions in the halld.registry.
    """
    for link_type in get_link_types():
        halld.models.LinkType.objects.get_or_create(name=link_type)
    for resource_type in get_resource_types():
        halld.models.ResourceType.objects.get_or_create(name=resource_type)
    for source_type in get_source_types():
        halld.models.SourceType.objects.get_or_create(name=source_type)

post_syncdb.connect(register_registry_types, sender=halld.models)
