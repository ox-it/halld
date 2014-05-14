import http.client
import io

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
        
        self.assertEqual(response.status_code, http.client.CREATED)

class FileViewTestCase(FileTestCase):
    pass
