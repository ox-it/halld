from hashlib import sha256

from django.core.cache import cache

from .. import exceptions
from ..models import Resource

class ResourceCache(object):
    def __init__(self, user):
        self.user = user
        self.resources = {}
    
    def get_resources(self, hrefs):
        hrefs_to_fetch = set(hrefs) - set(self.resources)
        resources = Resource.objects.filter(href__in=hrefs_to_fetch)
        for resource in resources:
            self.resources[resource.href] = resource
            hrefs_to_fetch.remove(resource.href)
        for href in hrefs_to_fetch:
            self.resources[href] = None
        missing_hrefs = [href for href in hrefs if not self.resources[href]]
        if missing_hrefs:
            raise exceptions.NoSuchResource(missing_hrefs)
        return (self.resources[href] for href in hrefs)

    def add_resources(self, resources):
        for resource in resources:
            self.resources[resource.href] = resource

    def get_resource(self, href):
        return next(self.get_resources([href]))

    def get_hal(self, href, exclude_links=False):
        resource = self.get_resource(href)
        cache_key = 'halld:hal:{0}:{1}'.format(self.user.username,
                                               sha256(resource.href.encode('utf-8')).hexdigest())
        hal = cache.get(cache_key)
        if hal and hal['_meta']['version'] == resource.version:
            return hal
        
        hal = resource.get_hal(self.user, self, exclude_links=exclude_links)
        cache.set(cache_key, hal)
        return hal