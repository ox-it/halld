from django.contrib.auth.models import User, AnonymousUser
from django.test import RequestFactory, TestCase

from .. import views

class ResourceTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(username='superuser',
                                                  email='superuser@example.com',
                                                  password='secret')
        self.resource_list_view = views.ResourceListView.as_view()
        self.resource_detail_view = views.ResourceDetailView.as_view()
        self.source_view = views.SourceDetailView.as_view()

    def tearDown(self):
        User.objects.all().delete()

    def testGetResourceList(self):
        request = self.factory.get('/snake')
        request.user = AnonymousUser()
        self.resource_list_view(request, 'snake')
