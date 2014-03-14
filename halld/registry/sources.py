import abc
import copy
import importlib
import threading

class SourceTypeDefinition(object, metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def name(self):
        pass

    contributed_types = frozenset()
    def get_contributed_types(self, source, data):
        return self.contributed_types

    @staticmethod
    def new(name, contributed_types=frozenset()):
        source_type = type(name.title() + 'SourceTypeDefinition',
                           (SourceTypeDefinition,),
                           {'name': name,
                            'contributed_types': contributed_types})
        return source_type()

    def get_hal(self, source, data):
        data = copy.copy(data)
        data['_meta'] = {'version': source.version,
                         'sourceType': source.type_id,
                         'modified': source.modified.isoformat(),
                         'created': source.created.isoformat()}
        data['_links'] = {
            'self': {'href': source.href},
            'resource': {'href': source.resource_id},
        }
        return data

    def data_from_hal(self, data):
        data.pop('_version', None)
        data.pop('_sourceType', None)
        data.pop('_links', None)
        return data

    def filter_data(self, user, source, data):
        return data

    def patch_acceptable(self, user, source, patch):
        return True

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