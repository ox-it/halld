import abc
import copy
import importlib
import threading
import ujson

import jsonpointer
import jsonschema

from halld import exceptions

class SourceTypeDefinition(object, metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def name(self):
        pass

    contributed_types = frozenset()
    def get_contributed_types(self, source, data):
        return self.contributed_types

    @classmethod
    def new(cls, name, contributed_types=frozenset()):
        source_type = type(name.title() + 'SourceTypeDefinition',
                           (cls,),
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

    def validate_data(self, source, data):
        """
        Override to perform validation, and raise a HALLDException if it fails.
        """

class SchemaValidatedSourceTypeDefinition(SourceTypeDefinition):
    @abc.abstractproperty
    def schema(self): pass

    @classmethod
    def new(cls, name, contributed_types=frozenset(), schema=None):
        source_type = type(name.title() + 'SourceTypeDefinition',
                           (cls,),
                           {'name': name,
                            'contributed_types': contributed_types,
                            'schema': schema})
        return source_type()

    @property
    def _schema(self):
        try:
            return _local.schemas[self.name]
        except (AttributeError, KeyError):
            if not hasattr(_local, 'schemas'):
                _local.schemas = {}
            if isinstance(self.schema, dict):
                _local.schemas[self.name] = self.schema
            elif isinstance(self.schema, str):
                with open(self.schema, 'r') as f:
                    _local.schemas[self.name] = ujson.load(f)
            else:
                raise AssertionError("Unexpected schema type ({0}) for source type {1}".format(type(self.schema),

            return _local.schemas[self.name]

    def validate_data(self, source, data):
        try:
            jsonschema.validate(data, self._schema)
        except jsonschema.ValidationError as e:
            raise exceptions.SourceValidationError(e.message,
                                                   jsonpointer.JsonPointer.from_parts(e.path).path,
                                                   jsonpointer.JsonPointer.from_parts(e.schema_path).path)

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