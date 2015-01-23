import http.client
import io
import json
import unittest

from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
import mock
from rest_framework.test import force_authenticate

from .base import TestCase
from ..models import Resource, Source
from ..files.models import ResourceFile
from ..files import views
from django.test.client import RequestFactory

class FileTestCase(TestCase):
    def setUp(self):
        super(FileTestCase, self).setUp()
        self.file_creation_view = views.FileCreationView.as_view()
        self.file_resource_detail_view = views.FileResourceDetailView.as_view()
        self.file_detail_view = views.FileDetailView.as_view()
        self.test_file = io.BytesIO(b"hello")
        self.test_file.name = 'hello.txt'

        self.another_file = io.BytesIO(b"goodbye")
        self.another_file.name = 'goodbye.rst'

    def tearDown(self):
        ResourceFile.objects.all().delete()
        super(FileTestCase, self).tearDown()

    def create_file_resource(self):
        request = self.factory.post("/document", {"file": self.test_file}, content_type='text/plain')
        force_authenticate(request, self.superuser)
        response = self.file_creation_view(request, "document")
        path = response['Location'][17:]
        identifier = path.split('/')[-1]
        return path, identifier

class FileCreationViewTestCase(FileTestCase):
    def testPostMultiPart(self):
        factory = RequestFactory()
        request = factory.post("/document", {"file": self.test_file})
        force_authenticate(request, self.superuser)
        response = self.file_creation_view(request, "document")
        self.check_creation_response(response)

    def testPostPlainFile(self):
        request = self.factory.post("/document",
                                    self.test_file.getvalue(),
                                    content_type='text/plain')
        request.user = self.superuser
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

class FileResourceDetailViewTestCase(FileTestCase):
    def testGet(self):
        path, identifier = self.create_file_resource()

        request = self.factory.get(path) # Trim scheme and host
        request.user = self.superuser
        response = self.file_resource_detail_view(request, 'document', identifier)

        data = json.loads(response.content.decode())
        file_link = data['_links'].get('describes')
        self.assertIsInstance(file_link, dict)
        self.assertEqual(request.build_absolute_uri(file_link.get('href')),
                         request.build_absolute_uri(reverse('halld-files:file-detail',
                                                            args=['document', identifier])))
        self.assertEqual(file_link.get('type'), 'text/plain')

class FileViewTestCase(FileTestCase):

    def testGet(self):
        path, identifier = self.create_file_resource()
        request = self.factory.get(path + '/file')
        request.user = self.superuser
        response = self.file_detail_view(request, 'document', identifier)
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertEqual(b''.join(response.streaming_content), self.test_file.getvalue())

    @mock.patch('halld.files.conf.USE_XSENDFILE', True)
    def testGetXSendFile(self):
        # X-Send-File is a header to tell the web server to send a file served
        # off disk.
        path, identifier = self.create_file_resource()
        request = self.factory.get(path + '/file')
        request.user = self.superuser
        response = self.file_detail_view(request, 'document', identifier)
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertEqual(response['X-Send-File'], ResourceFile.objects.get().file.path)

    def testPost(self):
        path, identifier = self.create_file_resource()
        request = self.factory.post(path + '/file',
                                    {'content_type': 'text/x-rst',
                                     'file': self.another_file})
        request.user = self.superuser
        response = self.file_detail_view(request, 'document', identifier)
        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        resource_file = ResourceFile.objects.get()
        self.assertEqual(resource_file.content_type, 'text/x-rst')
        self.assertEqual(resource_file.file.read(), self.another_file.getvalue())

    def testPut(self):
        path, identifier = self.create_file_resource()
        request = self.factory.put(path + '/file',
                                   self.another_file.read(),
                                   content_type='text/x-rst')
        request.user = self.superuser
        response = self.file_detail_view(request, 'document', identifier)
        self.assertEqual(response.status_code, http.client.NO_CONTENT)
        resource_file = ResourceFile.objects.get()
        self.assertEqual(resource_file.content_type, 'text/x-rst')
        self.assertEqual(resource_file.file.read(), self.another_file.getvalue())

    def testDelete(self):
        # It shouldn't be possible to delete a file like this
        path, identifier = self.create_file_resource()
        request = self.factory.delete(path + '/file')
        request.user = self.superuser
        response = self.file_detail_view(request, 'document', identifier)
        self.assertEqual(response.status_code, http.client.METHOD_NOT_ALLOWED)

class FileMetadataTestCase(TestCase):
    def upload_image(self):
        request = self.factory.post("/document", {"file": self.test_file})
        request.user = self.superuser
        response = self.file_creation_view(request, "document")
        path = response['Location'][17:]
        identifier = path.split('/')[-1]
        return path, identifier

    def testImage(self):
        pass