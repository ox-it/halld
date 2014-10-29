import mock
import unittest

from .base import TestCase

from .. import models
from ..data import Data

class LinkNormalizationTestCase(TestCase):
    def perform_normalizations(self, resource, data):
        for normalization in resource.get_normalizations():
            normalization(resource, data)

    def testInitialNormalization(self):
        resource = models.Resource(type_id='snake',
                                   identifier='cobra',
                                   creator=self.superuser)
        resource.save()
        data = Data({'eats': '/snake/python'})
        self.perform_normalizations(resource, data)
        self.assertEqual(data['eats'],
                         [{'href': 'http://testserver/snake/python'}])

    def testInboundAdded(self):
        cobra = models.Resource(type_id='snake',
                                identifier='cobra',
                                creator=self.superuser)
        cobra.save()

        python = models.Resource(type_id='snake',
                                 identifier='python',
                                 creator=self.superuser)
        python.generate_data = mock.Mock()
        python.generate_data.return_value = {'eats': [{'href': 'http://testserver/snake/cobra'}],
                                            '@id': 'http://testserver/id/snake/python'}
        python.save()

        cobra = models.Resource.objects.get(identifier='cobra')
        self.assertEqual(cobra.data.get('eatenBy'),
                         [{'href': python.href,
                           'inbound': True}])

    @unittest.expectedFailure
    def testAddLinkTitle(self):
        cobra = models.Resource(type_id='snake',
                                identifier='cobra',
                                creator=self.superuser)
        cobra.generate_data = mock.Mock()
        cobra.generate_data.return_value = {'title': 'Cobra',
                                            '@id': 'http://testserver/id/snake/python'}
        cobra.save()

        python = models.Resource(type_id='snake',
                                 identifier='python',
                                 creator=self.superuser)
        python.save()
        data = Data({'eats': '/snake/cobra'})
        self.perform_normalizations(python, data)
        self.assertEqual(data['eats'][0].get('title'),
                         'Cobra')
