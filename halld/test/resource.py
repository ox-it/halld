import json
import unittest

from rest_framework.test import force_authenticate

from .base import TestCase
from .. import models
from .. import response_data

class ResourceListTestCase(TestCase):
    def create_resources(self):
        # Will be defunct by default.
        self.defunct_resource = models.Resource.create(self.superuser, 'snake')
        self.extant_resource = models.Resource.create(self.superuser, 'snake')
        models.Source.objects.create(resource=self.extant_resource,
                                     type_id='science',
                                     data={'foo': 'bar'},
                                     author=self.superuser,
                                     committer=self.superuser)
        self.assertEqual(self.extant_resource.extant, True)

    def testGetResourceList(self):
        request = self.factory.get('/snake')
        force_authenticate(request, self.anonymous_user)
        response = self.resource_list_view(request, 'snake')
        self.assertIsInstance(response.data, response_data.ResourceList)

    def testDefunctResources(self):
        self.create_resources()
        request = self.factory.get('/snake?defunct=on&extant=off')
        request.user = self.anonymous_user
        response = self.resource_list_view(request, 'snake')
        self.assertIsInstance(response.data, response_data.ResourceList)
        self.assertEqual(response.data['paginator'].count, 1)
        self.assertEqual(next(response.data.resource_data)['self']['href'],
                         self.defunct_resource.href)

    def testExtantResources(self):
        self.create_resources()
        request = self.factory.get('/snake')
        force_authenticate(request, self.anonymous_user)
        response = self.resource_list_view(request, 'snake')
        self.assertIsInstance(response.data, response_data.ResourceList)
        self.assertEqual(response.data['paginator'].count, 1)
        self.assertEqual(next(response.data.resource_data)['self']['href'],
                         self.extant_resource.href)


class ResourceDetailTestCase(TestCase):
    def testViewResource(self):
        resource = models.Resource.create(self.superuser, 'snake')
        resource.data = {'title': 'Python'}
        resource.save(regenerate=False)

        request = self.factory.get('/snake/' + resource.identifier,
                                   headers={'Accept': 'application/hal+json'})
        force_authenticate(request, self.anonymous_user)
        response = self.resource_detail_view(request, 'snake', resource.identifier)
        self.assertEqual(response.data.data.get('title'), 'Python')

