import http

from django.test import TestCase, RequestFactory

from ..views import ResourceTypeListView, ResourceTypeDetailView

class ResourceTypeViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.resource_type_list_view = ResourceTypeListView.as_view()
        self.resource_type_detail_view = ResourceTypeDetailView.as_view()

    def testGetResourceTypeList(self):
        request = self.factory.get('/type')
        response = self.resource_type_list_view(request)
        self.assertEqual(response.status_code, http.client.OK)

    def testGetResourceTypeDetail(self):
        request = self.factory.get('/type/snake')
        response = self.resource_type_detail_view(request, 'snake')
        self.assertEqual(response.status_code, http.client.OK)
