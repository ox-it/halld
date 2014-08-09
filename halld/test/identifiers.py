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
