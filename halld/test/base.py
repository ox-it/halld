from django.contrib.auth.models import User
import django.test

from ..models import Changeset, Link, Identifier, Source, Resource
from .. import views

class TestCase(django.test.TestCase):
    def setUp(self):
        self.factory = django.test.RequestFactory()
        self.superuser = User.objects.create_superuser(username='superuser',
                                                       email='superuser@example.com',
                                                       password='secret')
        self.index_view = views.IndexView.as_view()
        self.by_identifier_view = views.ByIdentifierView.as_view()
        #self.source_type_view = views.SourceTypeView.as_view()
        self.source_list_view = views.SourceListView.as_view()
        self.source_view = views.SourceDetailView.as_view()
        self.resource_detail_view = views.ResourceDetailView.as_view()
        self.resource_list_view = views.ResourceListView.as_view()

    def tearDown(self):
        models = (User, Changeset, Link, Identifier, Source, Resource)
        for model in models:
            model.objects.all().delete()

    def create_resource(self, source_type='science'):
        request = self.factory.post('/snake')
        request.user = self.superuser
        response = self.resource_list_view(request, 'snake')
        resource_href = response['Location']
        identifier = resource_href.rsplit('/', 1)[1]
        source_href = resource_href + '/source/science'
        return response, source_href, identifier
