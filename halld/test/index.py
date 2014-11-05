import http

from django.contrib.auth.models import AnonymousUser

from .base import TestCase

class IndexViewTestCase(TestCase):
    def testGet(self):
        request = self.factory.get('/')
        request.user = AnonymousUser()
        response = self.index_view(request)
        self.assertEqual(response.status_code, http.client.OK)
