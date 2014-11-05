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

class ByIdentifierViewTestCase(TestCase):
    def testRetrieveSourceAllResources(self):
        _, id_one, _ = self.create_resource_and_source()
        _, id_two, _ = self.create_resource_and_source()
        data = {'scheme': 'snake',
                'allInScheme': True,
                'includeSources': ['science']}
        request = self.factory.post('/by-identifier', json.dumps(data), 'application/json')
        request.user = self.anonymous_user
        response = self.by_identifier_view(request)
        data = json.loads(response.content.decode())
        self.assert_(id_one in data)
        self.assert_(id_two in data)
        self.assert_('science' in data[id_one]['sources'])
        self.assert_('science' in data[id_two]['sources'])
