from django.test import TestCase
import mock

from ..data import Data
from .. import inference

class InferenceTestCase(TestCase):
    def testFirstOf(self):
        resource = mock.Mock()
        first_of = inference.FirstOf('/target', '/source/one', '/source/two')
        
        data = Data({'source': {'one': 'hello'}})
        first_of(resource, data)
        self.assertEqual(data.get('target'), 'hello')

        data = Data({'source': {'one': 'hello', 'two': 'goodbye'}})
        first_of(resource, data)
        self.assertEqual(data.get('target'), 'hello')

        data = Data({'source': {'two': 'goodbye'}})
        first_of(resource, data)
        self.assertEqual(data.get('target'), 'goodbye')

    def testFirstOfUnusualPointers(self):
        resource = mock.Mock()
        first_of = inference.FirstOf('/target', '/0', '/source/~0/~1/2/one', '/source/two')
        
        data = Data({'source': {'~': {'/': [4, 'eek', {'one': 'hello'}]},
                                'two': 'goodbye'}})
        first_of(resource, data)
        self.assertEqual(data.get('target'), 'hello')

    def testSet(self):
        resource = mock.Mock()
        set_inference = inference.Set('/target', '/source/one', '/source/two')
        
        # these should come back sorted
        data = Data({'source': {'one': ['Dog', 'Cat'], 'two': 'Mouse'}})
        set_inference(resource, data)
        self.assertEqual(data.get('target'),
                         ['Cat', 'Dog', 'Mouse'])

    def testSetAppend(self):
        resource = mock.Mock()
        set_inference = inference.Set('/target', '/source/one', '/source/two', append=True)

        data = Data({'target': 'Horse',
                     'source': {'one': ['Dog', 'Cat'], 'two': 'Mouse'}})
        set_inference(resource, data)
        self.assertEqual(data.get('target'),
                         ['Cat', 'Dog', 'Horse', 'Mouse'])
