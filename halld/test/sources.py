import http.client
import json
import mock
import uuid

from django.contrib.auth.models import User

from .base import TestCase
from .. import exceptions, models, views
from .. import response_data
from rest_framework.test import force_authenticate

class SourceManipulationTestCase(TestCase):
    def testGetUncreatedSource(self):
        request = self.factory.post('/snake')
        force_authenticate(request, self.superuser)
        response = self.resource_list_view(request, 'snake')
        identifier = response['Location'].rsplit('/', 1)[1]
        
        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        force_authenticate(request, self.superuser)
        
        with self.assertRaises(exceptions.NoSuchSource):
            response = self.source_detail_view(request, 'snake', identifier, 'science')

    @mock.patch('halld.signals.source_created')
    def testCreateSingleSource(self, source_created):
        title = 'Python'
        
        _, identifier = self.create_resource()
        source_href = 'http://testserver/snake/{}/source/science'.format(identifier)
        
        request = self.factory.put(source_href,
                                   data=json.dumps({'title': title}),
                                   content_type='application/hal+json')
        force_authenticate(request, self.superuser)
        response = self.source_detail_view(request, 'snake', identifier, 'science')

        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        assert source_created.send.called
        self.assertTrue(models.Source.objects.filter(href=source_href).exists())

        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        force_authenticate(request, self.superuser)
        response = self.source_detail_view(request, 'snake', identifier, 'science')
        
        source_data = response.data.data
        self.assertEqual(source_data['title'], title)
        self.assertEqual(source_data['_meta']['sourceType'], 'science')
        self.assertEqual(source_data['_meta']['version'], 1) # only just created

    @mock.patch('halld.signals.source_created')
    @mock.patch('halld.signals.source_deleted')
    def testDeleteAndResurrectSource(self, source_deleted, source_created):
        _, identifier = self.create_resource()

        # Create a source
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({}),
                                   content_type='application/hal+json')
        force_authenticate(request, self.superuser)
        self.source_detail_view(request, 'snake', identifier, 'science')

        # Delete it
        request = self.factory.delete('/snake/{}/source/science'.format(identifier))
        force_authenticate(request, self.superuser)
        response = self.source_detail_view(request, 'snake', identifier, 'science')

        assert source_deleted.send.called
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

        # Check it's gone
        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        force_authenticate(request, self.superuser)
        with self.assertRaises(exceptions.SourceDeleted):
            response = self.source_detail_view(request, 'snake', identifier, 'science')

        # Recreate it
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({'title': 'Cobra'}),
                                   content_type='application/hal+json')
        force_authenticate(request, self.superuser)
        response = self.source_detail_view(request, 'snake', identifier, 'science')
        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        assert source_created.send.called

        # And check it's there
        request = self.factory.get('/snake/{}/source/science'.format(identifier))
        force_authenticate(request, self.superuser)
        response = self.source_detail_view(request, 'snake', identifier, 'science')
        self.assertEqual(response.status_code, http.client.OK)

        source_data = response.data.data
        self.assertEqual(source_data.get('title'), 'Cobra')

    @mock.patch('halld.signals.source_deleted')
    def testDeleteWithNull(self, source_deleted):
        _, identifier = self.create_resource()

        # Create a source
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({'a': 'b'}),
                                   content_type='application/hal+json')
        force_authenticate(request, self.superuser)
        self.source_detail_view(request, 'snake', identifier, 'science')

        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps(None),
                                   content_type='application/hal+json')
        force_authenticate(request, self.superuser)
        response = self.source_detail_view(request, 'snake', identifier, 'science')

        assert source_deleted.send.called
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

    @mock.patch('halld.signals.source_created')
    def testPuttingNonDicts(self, source_created):
        _, identifier = self.create_resource()

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
            force_authenticate(request, self.superuser)

            with self.assertRaises(exceptions.SchemaValidationError):
                self.source_detail_view(request, 'snake', identifier, 'science')
            assert not source_created.called

    @mock.patch('halld.signals.source_changed')
    def testPatch(self, source_changed):
        _, identifier = self.create_resource()

        # Create a source
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({'foo': 'bar', 'baz': 'quux'}),
                                   content_type='application/hal+json')
        force_authenticate(request, self.superuser)
        self.source_detail_view(request, 'snake', identifier, 'science')

        # And PATCH it
        patch = [
            {'op': 'remove', 'path': '/foo'},
            {'op': 'replace', 'path': '/baz', 'value': 'xyzzy'},
        ]
        request = self.factory.patch('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps(patch),
                                   content_type='application/patch+json')
        force_authenticate(request, self.superuser)
        response = self.source_detail_view(request, 'snake', identifier, 'science')
        assert source_changed.send.called
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

        source = models.Source.objects.get()
        self.assertEqual(source.data, {'baz': 'xyzzy'})
        self.assertEqual(source.version, 2)

class SourceListViewTestCase(TestCase):
    def testGetEmpty(self):
        _, identifier = self.create_resource()

        request = self.factory.get('/snake/{}/source'.format(identifier))
        force_authenticate(request, self.superuser)
        response = self.source_list_view(request, 'snake', identifier)
        self.assertIsInstance(response.data, response_data.SourceList)
        self.assertIsInstance(response.data.get('sources'), list)
        self.assertEqual(len(response.data['sources']), 0)

    def testGetWithOne(self):
        _, identifier = self.create_resource()

        data = {'foo': 'bar', 'baz': 'quux'}
        # Create a source
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps(data),
                                   content_type='application/hal+json')
        force_authenticate(request, self.superuser)
        self.source_detail_view(request, 'snake', identifier, 'science')

        request = self.factory.get('/snake/{}/source'.format(identifier))
        force_authenticate(request, self.superuser)
        response = self.source_list_view(request, 'snake', identifier)
        self.assertIsInstance(response.data, response_data.SourceList)
        self.assertEqual(len(response.data['sources']), 1)
        source = response.data['sources'][0]
        self.assertEqual(source.data, data)

    def testPutMultiple(self):
        _, identifier = self.create_resource()

        science_data = {'foo': 'bar', '_meta': {'sourceType': 'science'}}
        mythology_data = {'baz': 'quux', '_meta': {'sourceType': 'mythology'}}
        data = {'_embedded': {'item': [science_data, mythology_data]}}

        request = self.factory.put('/snake/{}/source'.format(identifier),
                                   data=json.dumps(data),
                                   content_type='application/hal+json')
        force_authenticate(request, self.superuser)
        response = self.source_list_view(request, 'snake', identifier)
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

        science_data.pop('_meta'), mythology_data.pop('_meta')

        science_source = models.Source.objects.get(type_id='science')
        self.assertEqual(science_source.data, science_data)
        self.assertEqual(science_source.version, 1)

        mythology_source = models.Source.objects.get(type_id='mythology')
        self.assertEqual(mythology_source.data, mythology_data)
        self.assertEqual(mythology_source.version, 1)

    def testDelete(self):
        _, identifier = self.create_resource()

        data = {'foo': 'bar'}
        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps(data),
                                   content_type='application/hal+json')
        force_authenticate(request, self.superuser)
        self.source_detail_view(request, 'snake', identifier, 'science')

        request = self.factory.put('/snake/{}/source'.format(identifier),
                                   data=json.dumps({'_embedded': {'item': []}}),
                                   content_type='application/hal+json')
        force_authenticate(request, self.superuser)
        response = self.source_list_view(request, 'snake', identifier)
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

        science_source = models.Source.objects.get(type_id='science')
        self.assertEqual(science_source.data, None)
        self.assertEqual(science_source.version, 2)
        self.assertEqual(science_source.deleted, True)

class SourceTestCase(TestCase):
    def testResourceBecomesExtant(self):
        resource = models.Resource.create(self.superuser, 'snake')
        self.assertEqual(resource.extant, False)
        source = models.Source(resource=resource,
                               type_id='science',
                               author=self.superuser,
                               committer=self.superuser,
                               data={'foo': 'bar'})
        source.save()
        self.assertEqual(source.deleted, False)
        self.assertEqual(resource.extant, True)
        self.assertEqual(resource.data.get('foo'), 'bar')

    def testResourceBecomesDefunct(self):
        resource = models.Resource.create(self.superuser, 'snake')
        source = models.Source(resource=resource,
                               type_id='science',
                               author=self.superuser,
                               committer=self.superuser,
                               data={'foo': 'bar'})
        source.save()
        source.data = None
        source.save()
        self.assertEqual(resource.extant, False)

    def testMoveSource(self):
        original = models.Resource.create(self.superuser, 'snake')
        target = models.Resource.create(self.superuser, 'snake')
        source = models.Source.objects.create(resource=original,
                                              type_id='science',
                                              author=self.superuser,
                                              committer=self.superuser,
                                              data={'code': 'test'})
        self.assertEqual(original.data.get('code'), 'test')
        self.assertEqual(target.data.get('code'), None)

        request = self.factory.generic('MOVE',
                                       source.href,
                                       HTTP_LOCATION=target.href)
        force_authenticate(request, self.superuser)
        response = self.source_detail_view(request, 'snake', original.identifier, 'science')
        self.assertEqual(response.status_code, http.client.NO_CONTENT)

        original = models.Resource.objects.get(href=original.href)
        target = models.Resource.objects.get(href=target.href)

        self.assertEqual(original.data.get('code'), None)
        self.assertEqual(target.data.get('code'), 'test')

class AtomicTestCase(TestCase):
    def testDuplicatedIdentifier(self):
        resource = models.Resource.objects.create(type_id='snake', identifier='python', creator=self.superuser)
        identifier = models.Identifier.objects.create(resource=resource, scheme='misc', value='bar')

        _, identifier = self.create_resource()

        request = self.factory.put('/snake/{}/source/science'.format(identifier),
                                   data=json.dumps({'identifier': {'misc': 'bar'}}),
                                   content_type='application/hal+json')
        force_authenticate(request, self.superuser)
        with self.assertRaises(exceptions.DuplicatedIdentifier):
            response = self.source_detail_view(request, 'snake', identifier, 'science')

        # Make sure the source wasn't saved.
        self.assertEqual(models.Source.objects.filter(resource__identifier=identifier).count(),
                         0)
