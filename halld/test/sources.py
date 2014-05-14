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
        self.resource_detail_view = views.ResourceDetailView.as_view()
        self.resource_list_view = views.ResourceListView.as_view()

    def tearDown(self):
        User.objects.all().delete()

    def create_resource(self, source_type='science'):
        request = self.factory.post('/snake')
        request.user = self.user
        response = self.resource_list_view(request, 'snake')
        resource_href = response['Location']
        identifier = resource_href.rsplit('/', 1)[1]
        source_href = resource_href + '/source/science'
        return response, source_href, identifier

class SourceManipulationTestCase(SourceTestCase):
    def testGetUncreatedSource(self):
        request = self.factory.post('/snake')
        request.user = self.user
        response = self.resource_list_view(request, 'snake')
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

    @mock.patch('halld.signals.source_created')
    @mock.patch('halld.signals.source_deleted')
    def testDeleteAndResurrectSource(self, source_deleted, source_created):
        _, source_href, identifier = self.create_resource()

        # Create a source
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({}),
                                   content_type='application/json')
        request.user = self.user
        self.source_view(request, 'snake', identifier, 'science')

        # Delete it
        request = self.factory.delete('/snake/{}/source/science'.format(identifier))
        request.user = self.user
        response = self.source_view(request, 'snake', identifier, 'science')

        assert source_deleted.send.called
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

        # Check it's gone
        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        request.user = self.user
        response = self.source_view(request, 'snake', identifier, 'science')

        self.assertEqual(response.status_code, http.client.GONE)

        # Recreate it
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({}),
                                   content_type='application/json')
        request.user = self.user
        response = self.source_view(request, 'snake', identifier, 'science')
        self.assertEqual(response.status_code, http.client.OK)
        assert source_created.send.called

        # And check it's there
        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        request.user = self.user
        response = self.source_view(request, 'snake', identifier, 'science')
        self.assertEqual(response.status_code, http.client.OK)

        source_data = json.loads(response.content.decode())
        # Version 2 was the deleted version, so this should be version 3
        self.assertEqual(source_data['_meta']['version'], 3)

    @mock.patch('halld.signals.source_deleted')
    def testDeleteWithNull(self, source_deleted):
        _, source_href, identifier = self.create_resource()

        # Create a source
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({}),
                                   content_type='application/json')
        request.user = self.user
        self.source_view(request, 'snake', identifier, 'science')

        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps(None),
                                   content_type='application/json')
        request.user = self.user
        response = self.source_view(request, 'snake', identifier, 'science')

        assert source_deleted.send.called
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

    @mock.patch('halld.signals.source_created')
    def testPuttingNonDicts(self, source_created):
        _, source_href, identifier = self.create_resource()

        bad_data = (
            ['cat'],
            'hello',
            5,
            True,
            False,
        )

        for data in bad_data:
            request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                       data=json.dumps(data),
                                       content_type='application/json')
            request.user = self.user

            with self.assertRaises(exceptions.SourceValidationFailed):
                self.source_view(request, 'snake', identifier, 'science')
            assert not source_created.called

class AtomicTestCase(SourceTestCase):
    def testDuplicatedIdentifier(self):
        resource = models.Resource.objects.create(type_id='snake', identifier='python', creator=self.user)
        identifier = models.Identifier.objects.create(resource=resource, scheme='misc', value='bar')

        _, source_href, identifier = self.create_resource()

        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({'identifier': {'misc': 'bar'}}),
                                   content_type='application/json')
        request.user = self.user
        with self.assertRaises(exceptions.DuplicatedIdentifier):
            response = self.source_view(request, 'snake', identifier, 'science')

        # Make sure the source wasn't saved.
        self.assertEqual(models.Source.objects.filter(resource__identifier=identifier).count(),
                         0)
