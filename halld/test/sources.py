import http.client
import json
import mock
import uuid

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory

from .. import exceptions, models, views

class SourceTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(username='superuser',
                                                  email='superuser@example.com',
                                                  password='secret')
        #self.source_type_view = views.SourceTypeView.as_view()
        self.source_list_view = views.SourceListView.as_view()
        self.source_view = views.SourceDetailView.as_view()
        self.resource_view = views.ResourceView.as_view()
        self.resource_type_view = views.ResourceTypeView.as_view()

    def create_resource(self, source_type='science'):
        request = self.factory.post('/snake')
        request.user = self.user
        response = self.resource_type_view(request, 'snake')
        resource_href = response['Location']
        identifier = resource_href.rsplit('/', 1)[1]
        source_href = resource_href + '/source/science'
        return response, source_href, identifier

    def testGetUncreatedSource(self):
        request = self.factory.post('/snake')
        request.user = self.user
        response = self.resource_type_view(request, 'snake')
        identifier = response['Location'].rsplit('/', 1)[1]
        
        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        request.user = self.user
        
        with self.assertRaises(exceptions.NoSuchSource):
            response = self.source_view(request, 'snake', identifier, 'science')

    @mock.patch('halld.signals.source_created')
    def testCreateSingleSource(self, source_created):
        label = 'Python'
        
        _, source_href, identifier = self.create_resource()
        
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({'label': label}),
                                   content_type='application/json')
        request.user = self.user
        self.source_view(request, 'snake', identifier, 'science')

        assert source_created.send.called
        self.assertTrue(models.Source.objects.filter(href=source_href).exists())

        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        request.user = self.user
        response = self.source_view(request, 'snake', identifier, 'science')
        
        self.assertEqual(response['Content-type'], 'application/hal+json')
        source_data = json.loads(response.content.decode())
        self.assertEqual(source_data['label'], label)
        self.assertEqual(source_data['_meta']['sourceType'], 'science')
        self.assertEqual(source_data['_meta']['version'], 1) # only just created

    @mock.patch('halld.signals.source_deleted')
    def testDeleteSource(self, source_deleted):
        _, source_href, identifier = self.create_resource()
        
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({}),
                                   content_type='application/json')
        request.user = self.user
        self.source_view(request, 'snake', identifier, 'science')
        
        request = self.factory.delete('/snake/{}/source/science'.format(identifier))
        request.user = self.user
        response = self.source_view(request, 'snake', identifier, 'science')

        assert source_deleted.send.called

        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        
        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        request.user = self.user
        response = self.source_view(request, 'snake', identifier, 'science')
        
        self.assertEqual(response.status_code, http.client.GONE)