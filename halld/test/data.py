import copy
import json

from django.test import TestCase

from ..data import Data

class DataTestCase(TestCase):
    def testIdentifierGet(self):
        data = Data()
        data['stableIdentifier']['foo'] = 'bar'
        self.assertEqual(data['identifier'].get('foo'), 'bar')

    def testIdentifierGetItem(self):
        data = Data()
        data['stableIdentifier']['foo'] = 'bar'
        self.assertEqual(data['identifier']['foo'], 'bar')

    def testIdentifierCopy(self):
        data = Data()
        data['stableIdentifier']['foo'] = 'bar'
        import json
        identifier = copy.deepcopy(data['identifier'])
        self.assertEqual(identifier, {'foo': 'bar'})

    def testIdentifierJSON(self):
        data = Data()
        data['stableIdentifier']['foo'] = 'bar'
        actual = json.dumps(data._data, sort_keys=True)
        expected = json.dumps({'identifier': {'foo': 'bar'},
                               'stableIdentifier': {'foo': 'bar'}},
                              sort_keys=True)
        self.assertEqual(actual, expected)
