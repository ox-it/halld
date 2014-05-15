import http

from django.test import TestCase, RequestFactory

from ..views import IndexView

class IndexViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.index_view = IndexView.as_view()

    def testGet(self):
        request = self.factory.get('/')
        response = self.index_view(request)
        self.assertEqual(response.status_code, http.client.OK)
