import unittest
import uuid

from django.test import TestCase, RequestFactory

from halld import exceptions, models, views

class IdentifiersTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.by_identifier_view = views.ByIdentifierView.as_view()

    def testNotFound(self):
        request = self.factory.get('/by-identifier',
                                   {'scheme': 'thing',
                                    'value': 'something'})
        with self.assertRaises(exceptions.NoSuchIdentifier):
            self.by_identifier_view(request)

    @unittest.expectedFailure
    def testIdentifierCreatedForResourceType(self):
        identifier = uuid.uuid4().hex
        resource = models.Resource.objects.create(type_id='snake',
                                                  identifier=identifier)
        resource.save()

        assert models.Identifier.objects.filter(scheme='snake',
                                                value=identifier,
                                                resource=resource).exists()
