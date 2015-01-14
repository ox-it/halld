import abc
import importlib
from types import ModuleType, MappingProxyType

from django.apps.config import AppConfig
from django.utils.functional import cached_property

from halld.definitions import ResourceTypeDefinition, LinkTypeDefinition, SourceTypeDefinition

class HALLDConfig(AppConfig, metaclass=abc.ABCMeta):
    name = 'halld'
    verbose_name = 'HAL-LD'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abc.abstractproperty
    def resource_type_classes(self):
        return ()

    @abc.abstractproperty
    def link_type_classes(self):
        return ()

    @abc.abstractproperty
    def source_type_classes(self):
        return ()

    @cached_property
    def resource_types(self):
        return self._process_definitions('resource', ResourceTypeDefinition)

    @cached_property
    def link_types(self):
        return self._process_definitions('link', LinkTypeDefinition)

    @cached_property
    def source_types(self):
        return self._process_definitions('source', SourceTypeDefinition)

    def _process_definitions(self, name, cls):
        type_definitions = getattr(self, name + '_type_classes')
        # Check everything is actually a resource type definition
        assert all(issubclass(t, cls) for t in type_definitions)
        type_definitions = [t() for t in type_definitions]
        if cls == LinkTypeDefinition:
            type_definitions.extend([t.inverse() for t in type_definitions])
        # Check that no names are duplicated
        assert len(set(t.name for t in type_definitions)) == len(type_definitions)
        return MappingProxyType({t.name: t for t in type_definitions})

