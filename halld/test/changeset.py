import http
import json

from .. import exceptions
from .base import TestCase

from ..test_site.registry import SnakeResourceTypeDefinition

class ChangesetTestCase(TestCase):
    def testAddingUnsupportedSource(self):
        _, identifier = self.create_resource()
        changeset = {
            'updates': [{
                'method': 'PUT',
                'resourceHref': 'http://testserver/snake/' + identifier,
                'sourceType': 'conjecture',
                'data': {'wears': 'clothing'},
            }],
        }
        request = self.factory.post('/changeset',
                                    data=json.dumps(changeset),
                                    content_type='application/json')
        request.user = self.superuser

        with self.assertRaises(exceptions.MultipleErrors) as cm:
            self.changeset_list_view(request)

        self.assertEqual(cm.exception.status_code, http.client.BAD_REQUEST)
        error_json = cm.exception.as_hal()
        self.assertEqual(error_json['error'], 'multiple-errors')
        self.assertEqual(error_json['_embedded']['error'][0]['error'],
                         'incompatible-source-type')

    def testEditingSourceWithMissingResource(self):
        identifier = SnakeResourceTypeDefinition().generate_identifier()
        href = 'http://testserver/snake/' + identifier
        changeset = {
            'updates': [{
                'method': 'PUT',
                'resourceHref': href,
                'sourceType': 'conjecture',
                'data': {'wears': 'clothing'},
            }],
        }
        request = self.factory.post('/changeset',
                                    data=json.dumps(changeset),
                                    content_type='application/json')
        request.user = self.superuser

        with self.assertRaises(exceptions.SourceDataWithoutResource) as cm:
            self.changeset_list_view(request)
        error_json = cm.exception.as_hal()
        self.assertEqual(error_json['_links']['missingResources'],
                         [{'href': href}])
