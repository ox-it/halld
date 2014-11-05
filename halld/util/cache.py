import abc
from hashlib import sha256

from django.core.cache import cache

from .. import exceptions
from .. import models

class BaseCache(object, metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def Model(self): pass

    def __init__(self, object_cache):
        self.objs = {}
        self.object_cache = object_cache
    
    def get_many(self, pks, ignore_missing=False):
        pks_to_fetch = set(pks) - set(self.objs)
        if pks_to_fetch:
            objs = self.Model.objects.filter(href__in=pks_to_fetch)
            for obj in objs:
                self.objs[obj.pk] = obj
                pks_to_fetch.remove(obj.pk)
            for pks in pks_to_fetch:
                self.objs[pks] = None
        missing_pks = [pk for pk in pks if not self.objs[pk]]
        if not ignore_missing and missing_pks:
            raise exceptions.NoSuchResource(missing_pks)
        return (self.objs[pk] for pk in pks)

    def add_many(self, objs):
        for obj in objs:
            self.objs[obj.href] = obj

    def get(self, pk):
        return next(self.get_many([pk]))

class SourceCache(BaseCache):
    Model = models.Source

class ResourceCache(BaseCache):
    Model = models.Resource

    def __init__(self, object_cache, user):
        self.user = user
        super(ResourceCache, self).__init__(object_cache)

    def get_hal(self, href, exclude_links=False):
        resource = self.get(href)
        cache_key = 'halld:hal:{0}:{1}'.format(self.user.username,
                                               sha256(resource.href.encode('utf-8')).hexdigest())
        hal = cache.get(cache_key)
        if hal and hal['_meta']['version'] == resource.version:
            return hal
        
        hal = resource.get_hal(self.user, self.object_cache, exclude_links=exclude_links)
        cache.set(cache_key, hal)
        return hal

class ObjectCache(object):
    def __init__(self, user):
        self.source = SourceCache(self)
        self.resource = ResourceCache(self, user)
