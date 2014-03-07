import http.client

from django.test import TestCase, RequestFactory

from halld import exceptions, views

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

