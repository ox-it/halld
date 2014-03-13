import abc

import jsonpointer

from halld.registry import get_resource_types

class Inference(metaclass=abc.ABCMeta):
    inferred_keys = ()

    @abc.abstractmethod
    def __call__(self, resource, hal):
        pass

class Types(Inference):
    def __call__(self, resource, data):
        types = resource.get_type().get_contributed_types(resource, data)
        for source in resource.source_set.all():
            if not source.deleted:
                types |= source.get_type().get_contributed_types(source, source.data)
        data['@type'] = list(types)
        return data

class Identifiers(Inference):
    def __call__(self, resource, data):
        data['identifier'] = {}
        data['identifier'].update(resource.get_type().get_identifiers(resource, data))
        data['identifier'][resource.type_id] = resource.identifier
        # Don't copy type name identifiers
        for resource_type in get_resource_types().values():
            if resource_type.name != resource.type_id:
                data['identifier'].pop(resource_type.name, None)
        data['identifier']['uri'] = resource.get_absolute_uri(data)
        return data

class FromPointers(Inference):
    def __init__(self, target, *pointers):
        self.target = target
        self.inferred_keys = {target}
        self.pointers = pointers

class FirstOf(FromPointers):
    def __call__(self, resource, data):
        for pointer in self.pointers:
            try:
                result = jsonpointer.resolve_pointer(data, pointer)
                jsonpointer.set_pointer(data, self.target, result)
                break
            except jsonpointer.JsonPointerException:
                pass

class Set(FromPointers):
    def __init__(self, target, *pointers, append=False):
        self.append = append
        super(Set, self).__init__(target, *pointers)

    def __call__(self, resource, data):
        if self.append:
            result = set(jsonpointer.resolve_pointer(data, self.target, ()))
        else:
            result = set() 
        for pointer in self.pointers:
            value = jsonpointer.resolve_pointer(data, pointer, [])
            if not isinstance(value, (list, set)):
                value = {value}
            result.update(value)
        if result:
            jsonpointer.set_pointer(data, self.target, sorted(result))

class ResourceMeta(Inference):
    inferred_keys = ('catalogRecord','inCatalog')

    def __init__(self, catalog_uri):
        self.catalog_uri = catalog_uri

    def __call__(self, resource, hal):
        hal.update({
            'inCatalog': self.catalog_uri,
            'catalogRecord': {
                '@type': 'CatalogRecord',
                '@id': resource.get_absolute_url(),
                'created': resource.created,
                'modified': resource.modified,
                'catalog': self.catalog_uri,
            },
        })
