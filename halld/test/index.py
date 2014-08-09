import http

from .base import TestCase
from ..views import IndexView

class IndexViewTestCase(TestCase):
    def testGet(self):
        request = self.factory.get('/')
        response = self.index_view(request)
        self.assertEqual(response.status_code, http.client.OK)
