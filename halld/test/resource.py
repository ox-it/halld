import json

from .base import TestCase

from .. import models

class ResourceListTestCase(TestCase):
    def testGetResourceList(self):
        request = self.factory.get('/snake')
        request.user = self.anonymous_user
        self.resource_list_view(request, 'snake')

class ResourceDetailTestCase(TestCase):
    def testViewResource(self):
        resource = models.Resource.create(self.superuser, 'snake')
        resource.data = {'title': 'Python'}
        resource.save(regenerate=False)

        request = self.factory.get('/snake/' + resource.identifier,
                                   headers={'Accept': 'application/hal+json'})
        request.user = self.anonymous_user
        response = self.resource_detail_view(request, 'snake', resource.identifier)
        hal = json.loads(response.content.decode())
        self.assertEqual(hal.get('title'), 'Python')