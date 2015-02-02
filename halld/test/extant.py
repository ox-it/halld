import datetime

from django.contrib.auth.models import User
import mock

from .base import TestCase
from ..models import Resource, Source, Identifier, Link
from .. import response_data

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
        self.assertEqual(r.collect_data.call_count, 1)
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
        self.assertEqual(r.collect_data.call_count, 1)
        self.assertEqual(Identifier.objects.filter(resource=r,
                                                   scheme='foo',
                                                   value='bar').count(), 1)

class LinkTestCase(TestCase):
    def perform_test(self, self_extant, other_extant, link_name, resultant_link_name):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.superuser)
        Source.objects.create(resource=r, type_id='science',
                              author=self.superuser, committer=self.superuser,
                              data={'@extant': other_extant})
        s = Resource.objects.create(type_id='snake', identifier='cobra', creator=self.superuser)
        Source.objects.create(resource=s, type_id='science',
                              author=self.superuser, committer=self.superuser,
                              data={'@extant': self_extant,
                                    link_name: [{'href': 'http://testserver/snake/python'}]})
        s_rd = response_data.Resource(resource=s,
                                      object_cache=self.object_cache,
                                      user=self.anonymous_user)
        s_data = s_rd.data
        self.assertEqual(s_data[resultant_link_name],
                         [{'href': r.href}])
        if link_name != resultant_link_name:
            self.assertEqual(s_data.get(link_name), None)

    def testSelfDefunctTimeless(self):
        self.perform_test(False, True, 'timelessF', 'timelessF')
    def testOtherDefunctTimeless(self):
        self.perform_test(True, False, 'timelessF', 'timelessF')
    def testSelfDefunct(self):
        self.perform_test(False, True, 'eats', 'defunct:eats')
    def testOtherDefunct(self):
        self.perform_test(True, False, 'eats', 'defunct:eats')
    def testBothExtant(self):
        self.perform_test(True, True, 'eats', 'eats')
    def testBothDefunct(self):
        self.perform_test(False, False, 'eats', 'defunct:eats')
