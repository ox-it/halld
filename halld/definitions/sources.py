import abc
import copy
import importlib
import threading
import ujson

import jsonschema

from halld import exceptions

class SourceTypeDefinition(object, metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def name(self):
        pass

    contributed_tags = frozenset()
    def get_contributed_tags(self, source, data):
        return self.contributed_tags

    @classmethod
    def new(cls, name, contributed_types=frozenset()):
        source_type = type(name.title() + 'SourceTypeDefinition',
                           (cls,),
                           {'name': name,
                            'contributed_types': contributed_types})
        return source_type

    def get_inferences(self):
        return []

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
        # It needs to be a dict, but if it isn't, it'll get picked up later
        # in validate_data()
        if isinstance(data, dict):
            data.pop('_meta', None)
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
        if not isinstance(data, dict):
            raise exceptions.SourceDataMustBeObject

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
        return source_type

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
                                                                                               self.name))
            return _local.schemas[self.name]

    def validate_data(self, source, data):
        try:
            jsonschema.validate(data, self._schema)
        except jsonschema.ValidationError as e:
            raise exceptions.SchemaValidationError(e)
        super(SchemaValidatedSourceTypeDefinition, self).validate_data(source, data)
