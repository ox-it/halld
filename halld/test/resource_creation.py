import http.client
import uuid

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory

from halld import exceptions, models, views
from halld.registry import get_resource_type
from halld.test_site import registry

class ResourceHALTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(username='superuser',
                                                  email='superuser@example.com',
                                                  password='secret')
        self.resource_type_view = views.ResourceTypeView.as_view()
        self.source_view = views.SourceDetailView.as_view()
        self.resource_view = views.ResourceView.as_view()

    def testGetSourceWithMissingResource(self):
        request = self.factory.get('/snake/python/source/science')
        request.user = self.user

        with self.assertRaises(exceptions.SourceDataWithoutResource) as cm:
            self.source_view(request, 'snake', 'python', 'science')

        self.assertIsInstance(cm.exception.resource_type, registry.SnakeResourceTypeDefinition)
        self.assertEqual(cm.exception.identifier, 'python')

    def testForbiddenIdentifierAssignment(self):
        identifier = uuid.uuid4().hex
        request = self.factory.post('/snake/{}'.format(identifier))
        request.user = self.user

        with self.assertRaises(exceptions.CannotAssignIdentifier):
            self.resource_view(request, 'snake', identifier)

    def testAllowedIdentifierAssignment(self):
        identifier = uuid.uuid4().hex
        request = self.factory.post('/penguin/{}'.format(identifier))
        request.user = self.user

        try:
            response = self.resource_view(request, 'penguin', identifier)
        except exceptions.CannotAssignIdentifier:
            self.fail("Should have been able to assign identifier")
        else:
            self.checkResourceExists('penguin', response)

    def testInvalidIdentifierAssignment(self):
        # Default set-up requires identifiers be UUIDs
        request = self.factory.post('/snake/python')
        request.user = self.user

        with self.assertRaises(exceptions.NotValidIdentifier):
            self.resource_view(request, 'snake', 'python')

    def testCreateFromCollection(self):
        request = self.factory.post('/snake')
        request.user = self.user

        response = self.resource_type_view(request, 'snake')
        self.checkResourceExists('snake', response)

    def checkResourceExists(self, resource_type, response):
        resource_type = get_resource_type(resource_type)
        self.assertEqual(response.status_code, http.client.CREATED)
        href = response['Location']
        assert href.startswith(resource_type.base_url)
        identifier = href[len(resource_type.base_url):]
        
        try:
            models.Resource.objects.get(href=href)
        except models.Resource.DoesNotExist:
            self.fail("Resource wasn't created")
        
        request = self.factory.get('/{}/{}'.format(resource_type.name, identifier))
        request.user = self.user

        response = self.resource_view(request, resource_type.name, identifier)
        self.assertEqual(response.status_code, http.client.OK)