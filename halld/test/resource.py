from .base import TestCase

class ResourceListTestCase(TestCase):
    def testGetResourceList(self):
        request = self.factory.get('/snake')
        request.user = self.anonymous_user
        self.resource_list_view(request, 'snake')
