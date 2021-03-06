import json
import unittest
import uuid

from django.db import transaction

from halld import exceptions, models, views

from .base import TestCase

class IdentifiersTestCase(TestCase):
    def testNotFound(self):
        query = {'scheme': 'thing',
                 'values': ['something']}
        request = self.factory.generic('POST',
                                       '/by-identifier',
                                       json.dumps(query),
                                       content_type='application/json')
        response = self.by_identifier_view(request)

    @unittest.expectedFailure
    @transaction.atomic # to contain the DB exception
    def testIdentifierCreatedForResourceType(self):
        identifier = uuid.uuid4().hex
        resource = models.Resource.objects.create(type_id='snake',
                                                  identifier=identifier)
        resource.save()

        assert models.Identifier.objects.filter(scheme='snake',
                                                value=identifier,
                                                resource=resource).exists()

class URITemplateTestCase(TestCase):
    def testURITemplate(self):
        resource = models.Resource.create(self.superuser, 'uri-templated')
        self.assertEqual(resource.uri, 'http://id.example.org/resource/' + resource.identifier)


class ByIdentifierViewTestCase(TestCase):
    def testRetrieveSourceAllResources(self):
        _, id_one, _ = self.create_resource_and_source()
        _, id_two, _ = self.create_resource_and_source()
        data = {'scheme': 'snake',
                'allInScheme': True,
                'includeSources': ['science']}
        request = self.factory.post('/by-identifier', json.dumps(data),
                                    content_type='application/json')
        request.user = self.anonymous_user
        response = self.by_identifier_view(request)
        self.assert_(id_one in response.data['results'])
        self.assert_(id_two in response.data['results'])
        self.assert_('science' in response.data['results'][id_one]['sources'])
        self.assert_('science' in response.data['results'][id_two]['sources'])
