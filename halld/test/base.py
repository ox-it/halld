from django.contrib.auth.models import User, AnonymousUser
from django.core.cache import cache
import django.test

from rest_framework.test import APIRequestFactory, force_authenticate

from ..models import Changeset, Link, Identifier, Source, Resource
from .. import views
from ..util.cache import ObjectCache

class TestCase(django.test.TransactionTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.factory = APIRequestFactory()
        self.superuser = User.objects.create_superuser(username='superuser',
                                                       email='superuser@example.com',
                                                       password='secret')
        self.anonymous_user = AnonymousUser
        self.object_cache = ObjectCache(self.anonymous_user)
        self.changeset_list_view = views.ChangesetListView.as_view()
        self.index_view = views.IndexView.as_view()
        self.by_identifier_view = views.ByIdentifierView.as_view()
        #self.source_type_view = views.SourceTypeView.as_view()
        self.source_list_view = views.SourceListView.as_view()
        self.source_detail_view = views.SourceDetailView.as_view()
        self.resource_detail_view = views.ResourceDetailView.as_view()
        self.resource_list_view = views.ResourceListView.as_view()

    def create_resource(self):
        request = self.factory.post('/snake')
        force_authenticate(request, self.superuser)
        response = self.resource_list_view(request, 'snake')
        resource_href = response['Location']
        identifier = resource_href.rsplit('/', 1)[1]
        source_href = resource_href + '/source/science'
        return response, identifier

    def create_resource_and_source(self, source_type='science'):
        response, identifier = self.create_resource()
        resource_href = response['Location']
        source_href = resource_href + '/source/science'
        request = self.factory.put(source_href, '{}', content_type='application/hal+json')
        request.user = self.superuser
        response = self.source_detail_view(request, 'snake', identifier, source_type)
        return response, identifier, source_href
