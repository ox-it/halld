import unittest

from .base import TestCase
from .. import models
from ..util.cache import ObjectCache

class HALTestCase(TestCase):
    # This all needs redoing to test the hal_json d-r-f renderer
    @unittest.expectedFailure
    def testLinks(self):
        python = models.Resource.create(self.superuser, 'snake')
        python.data = {'title': 'Python'}
        python.save(regenerate=False)
        
        cobra = models.Resource.create(self.superuser, 'snake')
        cobra.data = {'title': 'Cobra',
                      'eats': [{'href': python.href}]}
        cobra.save(regenerate=False)
        
        object_cache = ObjectCache(self.anonymous_user)
        object_cache.resource.add_many([python, cobra])
        
        cobra_hal = object_cache.resource.get_hal(cobra.href)
