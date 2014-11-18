import datetime

from django.contrib.auth.models import User
import mock

from .base import TestCase
from ..models import Resource, Identifier, Link

class ExtantTestCase(TestCase):
    def testExtantFalse(self):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.superuser)
        r.data = {'@id': 'http://testserver/id/snake/python',
                  '@extant': False}
        r.update_denormalized_fields()
        self.assertEqual(r.extant, False)

    def testNotYetCurrent(self):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.superuser)
        r.data = {'@id': 'http://testserver/id/snake/python',
                  # This resource starts existing two days from now.
                  '@startDate': (datetime.date.today() + datetime.timedelta(2)).isoformat()}
        r.update_denormalized_fields()
        self.assertEqual(r.extant, False)

    def testBeenAndGone(self):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.superuser)
        r.data = {'@id': 'http://testserver/id/snake/python',
                  # This resource stopped existing two days ago.
                  '@endDate': (datetime.date.today() - datetime.timedelta(2)).isoformat()}
        r.update_denormalized_fields()
        self.assertEqual(r.extant, False)

    @mock.patch('halld.signals.request_future_resource_generation')
    def testFutureExistenceSignal(self, request_future_resource_generation):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.superuser)
        self.assertFalse(request_future_resource_generation.called)
        r.collect_data = mock.Mock()
        r.collect_data.return_value = {'@id': 'http://testserver/id/snake/python',
                                       # This resource starts existing two days from now.
                                       '@startDate': (datetime.date.today() + datetime.timedelta(2)).isoformat()}
        r.save()
        self.assertEqual(r.collect_data.call_count, 1)
        request_future_resource_generation.send.assert_called_once_with(r, when=r.start_date)

    def testNoIdentifiersForNonExtantResources(self):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.superuser)
        r.collect_data = mock.Mock()
        r.collect_data.return_value = {'@id': 'http://testserver/id/snake/python',
                                       '@extant': False,
                                       'identifier': {'foo': 'bar'}}
        r.save()
        r.collect_data.assert_called_once_with()
        self.assertEqual(Identifier.objects.filter(resource=r,
                                                   scheme='foo',
                                                   value='bar').count(), 0)

    def testStableIdentifiersForNonExtantResources(self):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.superuser)
        r.collect_data = mock.Mock()
        r.collect_data.return_value = {'@id': 'http://testserver/id/snake/python',
                                       '@extant': False,
                                       'stableIdentifier': {'foo': 'bar'}}
        r.save()
        r.collect_data.assert_called_once_with()
        self.assertEqual(Identifier.objects.filter(resource=r,
                                                   scheme='foo',
                                                   value='bar').count(), 1)
