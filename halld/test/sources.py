import http.client
import json
import mock
import uuid

from django.contrib.auth.models import User

from .base import TestCase
from .. import exceptions, models, views

class SourceManipulationTestCase(TestCase):
    def testGetUncreatedSource(self):
        request = self.factory.post('/snake')
        request.user = self.superuser
        response = self.resource_list_view(request, 'snake')
        identifier = response['Location'].rsplit('/', 1)[1]
        
        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        request.user = self.superuser
        
        with self.assertRaises(exceptions.NoSuchSource):
            response = self.source_view(request, 'snake', identifier, 'science')

    @mock.patch('halld.signals.source_created')
    def testCreateSingleSource(self, source_created):
        title = 'Python'
        
        _, source_href, identifier = self.create_resource()
        
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({'title': title}),
                                   content_type='application/hal+json')
        request.user = self.superuser
        self.source_view(request, 'snake', identifier, 'science')

        assert source_created.send.called
        self.assertTrue(models.Source.objects.filter(href=source_href).exists())

        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        request.user = self.superuser
        response = self.source_view(request, 'snake', identifier, 'science')
        
        self.assertEqual(response['Content-type'], 'application/hal+json')
        source_data = json.loads(response.content.decode())
        self.assertEqual(source_data['title'], title)
        self.assertEqual(source_data['_meta']['sourceType'], 'science')
        self.assertEqual(source_data['_meta']['version'], 1) # only just created

    @mock.patch('halld.signals.source_created')
    @mock.patch('halld.signals.source_deleted')
    def testDeleteAndResurrectSource(self, source_deleted, source_created):
        _, source_href, identifier = self.create_resource()

        # Create a source
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({}),
                                   content_type='application/hal+json')
        request.user = self.superuser
        self.source_view(request, 'snake', identifier, 'science')

        # Delete it
        request = self.factory.delete('/snake/{}/source/science'.format(identifier))
        request.user = self.superuser
        response = self.source_view(request, 'snake', identifier, 'science')

        assert source_deleted.send.called
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

        # Check it's gone
        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        request.user = self.superuser
        response = self.source_view(request, 'snake', identifier, 'science')

        self.assertEqual(response.status_code, http.client.GONE)

        # Recreate it
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({}),
                                   content_type='application/hal+json')
        request.user = self.superuser
        response = self.source_view(request, 'snake', identifier, 'science')
        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        assert source_created.send.called

        # And check it's there
        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        request.user = self.superuser
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
                                   content_type='application/hal+json')
        request.user = self.superuser
        self.source_view(request, 'snake', identifier, 'science')

        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps(None),
                                   content_type='application/hal+json')
        request.user = self.superuser
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
                                       content_type='application/hal+json')
            request.user = self.superuser

            with self.assertRaises(exceptions.SchemaValidationError):
                self.source_view(request, 'snake', identifier, 'science')
            assert not source_created.called

    @mock.patch('halld.signals.source_changed')
    def testPatch(self, source_changed):
        _, source_href, identifier = self.create_resource()

        # Create a source
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({'foo': 'bar', 'baz': 'quux'}),
                                   content_type='application/hal+json')
        request.user = self.superuser
        self.source_view(request, 'snake', identifier, 'science')

        # And PATCH it
        patch = [
            {'op': 'remove', 'path': '/foo'},
            {'op': 'replace', 'path': '/baz', 'value': 'xyzzy'},
        ]
        request = self.factory.patch('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps(patch),
                                   content_type='application/patch+json')
        request.user = self.superuser
        response = self.source_view(request, 'snake', identifier, 'science')
        assert source_changed.send.called
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

        source = models.Source.objects.get()
        self.assertEqual(source.data, {'baz': 'xyzzy'})
        self.assertEqual(source.version, 2)

class SourceListViewTestCase(TestCase):
    def testGetEmpty(self):
        _, source_href, identifier = self.create_resource()

        request = self.factory.get('/snake/{}/source'.format(identifier))
        request.user = self.superuser
        response = self.source_list_view(request, 'snake', identifier)
        data = json.loads(response.content.decode())
        self.assertEqual(data, {'_embedded': {}})

    def testGetWithOne(self):
        _, source_href, identifier = self.create_resource()

        data = {'foo': 'bar', 'baz': 'quux'}
        # Create a source
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps(data),
                                   content_type='application/hal+json')
        request.user = self.superuser
        self.source_view(request, 'snake', identifier, 'science')

        request = self.factory.get('/snake/{}/source'.format(identifier))
        request.user = self.superuser
        response = self.source_list_view(request, 'snake', identifier)
        source_list = json.loads(response.content.decode())
        # We don't care about the metadata or links
        source_list['_embedded']['source:science'].pop('_meta')
        source_list['_embedded']['source:science'].pop('_links')
        self.assertEqual(source_list, {'_embedded': {'source:science': data}})

    def testPutMultiple(self):
        _, source_href, identifier = self.create_resource()

        science_data = {'foo': 'bar'}
        mythology_data = {'baz': 'quux'}
        data = {'_embedded': {'source:science': science_data,
                              'source:mythology': mythology_data}}

        request = self.factory.put('/snake/{}/source'.format(identifier),
                                   data=json.dumps(data),
                                   content_type='application/hal+json')
        request.user = self.superuser
        response = self.source_list_view(request, 'snake', identifier)
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

        science_source = models.Source.objects.get(type_id='science')
        self.assertEqual(science_source.data, science_data)
        self.assertEqual(science_source.version, 1)

        mythology_source = models.Source.objects.get(type_id='mythology')
        self.assertEqual(mythology_source.data, mythology_data)
        self.assertEqual(mythology_source.version, 1)

    def testDelete(self):
        _, source_href, identifier = self.create_resource()

        data = {'foo': 'bar'}
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps(data),
                                   content_type='application/hal+json')
        request.user = self.superuser
        self.source_view(request, 'snake', identifier, 'science')

        request = self.factory.put('/snake/{}/source'.format(identifier),
                                   data=json.dumps({'_embedded': {'source:science': None}}),
                                   content_type='application/hal+json')
        request.user = self.superuser
        response = self.source_list_view(request, 'snake', identifier)
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

        science_source = models.Source.objects.get(type_id='science')
        self.assertEqual(science_source.data, {})
        self.assertEqual(science_source.version, 2)
        self.assertEqual(science_source.deleted, True)

class AtomicTestCase(TestCase):
    def testDuplicatedIdentifier(self):
        resource = models.Resource.objects.create(type_id='snake', identifier='python', creator=self.superuser)
        identifier = models.Identifier.objects.create(resource=resource, scheme='misc', value='bar')

        _, source_href, identifier = self.create_resource()

        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({'identifier': {'misc': 'bar'}}),
                                   content_type='application/hal+json')
        request.user = self.superuser
        with self.assertRaises(exceptions.DuplicatedIdentifier):
            response = self.source_view(request, 'snake', identifier, 'science')

        # Make sure the source wasn't saved.
        self.assertEqual(models.Source.objects.filter(resource__identifier=identifier).count(),
                         0)
