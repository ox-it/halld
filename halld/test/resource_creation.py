import http.client
import uuid

from halld import exceptions, models, get_halld_config

from .base import TestCase

class ResourceHALTestCase(TestCase):

    def testGetSourceWithMissingResource(self):
        request = self.factory.get('/snake/python/source/science')
        request.user = self.superuser

        with self.assertRaises(exceptions.SourceDataWithoutResource) as cm:
            self.source_detail_view(request, 'snake', 'python', 'science')

        self.assertEqual(set(cm.exception.hrefs),
                         {'http://testserver/snake/python'})

    def testForbiddenIdentifierAssignment(self):
        identifier = uuid.uuid4().hex
        request = self.factory.post('/snake/{}'.format(identifier))
        request.user = self.superuser

        with self.assertRaises(exceptions.CannotAssignIdentifier):
            self.resource_detail_view(request, 'snake', identifier)

    def testAllowedIdentifierAssignment(self):
        identifier = uuid.uuid4().hex
        request = self.factory.post('/penguin/{}'.format(identifier))
        request.user = self.superuser

        try:
            response = self.resource_detail_view(request, 'penguin', identifier)
        except exceptions.CannotAssignIdentifier:
            self.fail("Should have been able to assign identifier")
        else:
            self.checkResourceExists('penguin', response)

    def testInvalidIdentifierAssignment(self):
        # Default set-up requires identifiers be UUIDs
        request = self.factory.post('/snake/python')
        request.user = self.superuser

        with self.assertRaises(exceptions.NotValidIdentifier):
            self.resource_detail_view(request, 'snake', 'python')

    def testCreateFromCollection(self):
        request = self.factory.post('/snake')
        request.user = self.superuser

        response = self.resource_list_view(request, 'snake')
        self.checkResourceExists('snake', response)

    def checkResourceExists(self, resource_type, response):
        resource_type = get_halld_config().resource_types[resource_type]
        self.assertEqual(response.status_code, http.client.CREATED)
        href = response['Location']
        assert href.startswith(resource_type.base_url)
        identifier = href[len(resource_type.base_url):]
        
        try:
            models.Resource.objects.get(href=href)
        except models.Resource.DoesNotExist:
            self.fail("Resource wasn't created")
        
        request = self.factory.get('/{}/{}'.format(resource_type.name, identifier))
        request.user = self.superuser

        response = self.resource_detail_view(request, resource_type.name, identifier)
        self.assertEqual(response.status_code, http.client.OK)
