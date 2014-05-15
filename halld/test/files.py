import http.client
import io
import unittest

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory

from ..models import Resource, Source
from ..files.models import ResourceFile
from ..files import views

class FileTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(username='superuser',
                                                  email='superuser@example.com',
                                                  password='secret')
        self.file_creation_view = views.FileCreationView.as_view()
        self.file_view = views.FileView.as_view()
        self.test_file = io.BytesIO(b"hello")
        self.test_file.name = 'hello.txt'

    def tearDown(self):
        User.objects.all().delete()
        Source.objects.all().delete()
        ResourceFile.objects.all().delete()
        Resource.objects.all().delete()

class FileCreationViewTestCase(FileTestCase):
    def testPostMultiPart(self):
        request = self.factory.post("/document", {"file": self.test_file})
        request.user = self.user
        response = self.file_creation_view(request, "document")
        self.check_creation_response(response)

    def testPostPlainFile(self):
        request = self.factory.post("/document",
                                    self.test_file.getvalue(),
                                    content_type='text/plain')
        request.user = self.user
        response = self.file_creation_view(request, "document")
        self.check_creation_response(response)

    def check_creation_response(self, response):
        self.assertEqual(response.status_code, http.client.CREATED)
        location = response['Location']
        assert location.startswith("http://testserver/document/")

        try:
            resource = Resource.objects.get(type_id='document')
        except Resource.DoesNotExist:
            assert False, "Resource for file not created."

        try:
            resource_file = ResourceFile.objects.get(resource=resource)
        except ResourceFile.DoesNotExist:
            assert False, "ResourceFile not created."

        # This will have been inferred client-side from our .txt file name
        self.assertEqual(resource_file.content_type, 'text/plain')
        # And make sure the right thing ended up in our file.
        self.assertEqual(resource_file.file.read(), self.test_file.getvalue())

class FileViewTestCase(FileTestCase):
    def testPostMultiPart(self):
        request = self.factory.post("/document", {"file": self.test_file})
        request.user = self.user
        response = self.file_creation_view(request, "document")

        request = self.factory.get(response['Location'][17:]) # Trim scheme and host
        # TODO: more assertions
