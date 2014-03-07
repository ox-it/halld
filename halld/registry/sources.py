import abc
import importlib
import threading

class SourceTypeDefinition(object, metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def name(self):
        pass

    @staticmethod
    def new(name):
        source_type = type(name.title() + 'SourceTypeDefinition',
                           (SourceTypeDefinition,),
                           {'name': name})
        return source_type()

_local = threading.local()
def get_source_types():
    try:
        return _local.source_types
    except AttributeError:
        from django.conf import settings
        source_types = {}
        for source_type in settings.SOURCE_TYPES:
            if isinstance(source_type, str):
                mod_name, attr_name = source_type.rsplit('.', 1)
                source_type = getattr(importlib.import_module(mod_name), attr_name)()
            source_types[source_type.name] = source_type
        _local.source_types = source_types
        return source_types

def get_source_type(name):
    return get_source_types()[name]