import abc
import collections
import logging

import jsonpointer

from . import models

logger = logging.getLogger(__name__)

class Inference(metaclass=abc.ABCMeta):
    inferred_keys = ()

    @abc.abstractmethod
    def __call__(self, resource, hal):
        pass

class Tags(Inference):
    def __call__(self, resource, data, **kwargs):
        tags = resource.get_type().get_contributed_tags(resource, data)
        for source in resource.cached_source_set:
            if not source.deleted:
                tags |= source.get_type().get_contributed_tags(source, source.data)
        data['tags'] = list(tags | set(data.get('tags', ())))
        return data

class FromPointers(Inference):
    def __init__(self, target, *pointers):
        self.target = jsonpointer.JsonPointer(target)
        self.inferred_keys = {target}
        self.pointers = list(map(jsonpointer.JsonPointer, pointers))

class FirstOf(FromPointers):
    def __init__(self, target, *pointers, update=False):
        self.update = update
        super(FirstOf, self).__init__(target, *pointers)

    def __call__(self, resource, data, **kwargs):
        for pointer in self.pointers:
            try:
                result = data.resolve(pointer)
            except jsonpointer.JsonPointerException:
                continue
            if self.update:
                if not isinstance(result, dict):
                    continue
                try:
                    target = data.resolve(self.target)
                    if not isinstance(target, dict):
                        logger.warning("FirstOf target %s is not a dict", self.target)
                        return
                    target.update(result)
                except jsonpointer.JsonPointerException:
                    data.set(self.target, result)
            else:
                data.set(self.target, result)
            return

    def __repr__(self):
        return 'FirstOf({!r}, {}{})'.format(self.target,
                                            ', '.join(map(repr, self.pointers)),
                                            ', update=True' if self.update else '')

class Lookup(FromPointers):
    def __init__(self, target, scheme, *pointers):
        self.target = jsonpointer.JsonPointer(target)
        self.scheme = scheme
        self.pointers = list(map(jsonpointer.JsonPointer, pointers))

    def __call__(self, resource, data, prefetched_data, **kwargs):
        for pointer in self.pointers:
            try:
                value = data.resolve(pointer)
                break
            except jsonpointer.JsonPointerException:
                continue
        else:
            return

        try:
            if 'identifiers' in prefetched_data:
                other = prefetched_data['identifiers'][(self.scheme, value)]
            else:
                other = models.Identifier.objects.select_related('resource').get(scheme=self.scheme,
                                                                                 value=value).resource.href
        except models.Identifier.DoesNotExist:
            logger.warning("Can't lookup identifier '%s' in scheme '%s' for resource '%s' and pointer '%s'",
                           value, self.scheme,
                           resource.href, pointer.path)
        else:
            data.set(self.target, other)

class Set(FromPointers):
    """
    Inference that unions the data from a set of source pointers.
    
    Source values that aren't lists are converted to one-element lists, and
    the results are sorted. An optional `append` argument can be passed to the
    constructor, which includes the pre-existing values at the target in the
    result.
    """
    def __init__(self, target, *pointers, append=False):
        if append:
            pointers += (target,)
        super(Set, self).__init__(target, *pointers)

    def __call__(self, resource, data, **kwargs):
        result = set()
        for pointer in self.pointers:
            value = data.resolve(pointer, [])
            if isinstance(value, collections.defaultdict):
                continue
            if not isinstance(value, (list, set)):
                value = {value}
            result.update(value)
        if result:
            data.set(self.target, sorted(result))

class ResourceMeta(Inference):
    inferred_keys = ('catalogRecord','inCatalog')

    def __init__(self, catalog_uri):
        self.catalog_uri = catalog_uri

    def __call__(self, resource, data, **kwargs):
        data.update({
            'inCatalog': self.catalog_uri,
            'catalogRecord': {
                '@type': 'CatalogRecord',
                '@id': resource.get_absolute_url(),
                'created': resource.created,
                'modified': resource.modified,
                'catalog': self.catalog_uri,
            },
        })
