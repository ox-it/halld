import datetime

from django.test import TestCase
import mock

from ..models import Resource, Identifier, Link

class ExtantTestCase(TestCase):
    def tearDown(self):
        Resource.objects.all().delete()

    def testExtantFalse(self):
        r = Resource.objects.create(type_id='snake', identifier='python')
        r.raw_data = {'@id': 'http://testserver/id/snake/python',
                      '@extant': False}
        r.update_data()
        self.assertEqual(r.extant, False)

    def testNotYetCurrent(self):
        r = Resource.objects.create(type_id='snake', identifier='python')
        r.raw_data = {'@id': 'http://testserver/id/snake/python',
                      # This resource starts existing two days from now.
                      '@startDate': (datetime.date.today() + datetime.timedelta(2)).isoformat()}
        r.update_data()
        self.assertEqual(r.extant, False)

    def testBeenAndGone(self):
        r = Resource.objects.create(type_id='snake', identifier='python')
        r.raw_data = {'@id': 'http://testserver/id/snake/python',
                      # This resource stopped existing two days ago.
                      '@endDate': (datetime.date.today() - datetime.timedelta(2)).isoformat()}
        r.update_data()
        self.assertEqual(r.extant, False)

    @mock.patch('halld.signals.request_future_resource_generation')
    def testFutureExistenceSignal(self, request_future_resource_generation):
        r = Resource.objects.create(type_id='snake', identifier='python')
        self.assertFalse(request_future_resource_generation.called)
        r.regenerate = mock.Mock() # So that saving doesn't wipe out our hacked-in raw_data
        r.raw_data = {'@id': 'http://testserver/id/snake/python',
                      # This resource starts existing two days from now.
                      '@startDate': (datetime.date.today() + datetime.timedelta(2)).isoformat()}
        r.save()
        self.assertEqual(r.regenerate.call_count, 1)
        request_future_resource_generation.send.assert_called_once_with(r, when=r.start_date)

    def testNoIdentifiersForNonExtantResources(self):
        r = Resource.objects.create(type_id='snake', identifier='python')
        r.regenerate = mock.Mock() # So that saving doesn't wipe out our hacked-in raw_data
        r.raw_data = {'@id': 'http://testserver/id/snake/python',
                      '@extant': False,
                      'identifier': {'foo': 'bar'}}
        r.save()
        self.assertEqual(Identifier.objects.filter(resource=r,
                                                   scheme='foo',
                                                   value='bar').count(), 0)

    def testNonExtantLink(self):
        anaconda = Resource.objects.create(type_id='snake', identifier='anaconda')
        r = Resource.objects.create(type_id='snake', identifier='python')
        r.regenerate = mock.Mock() # So that saving doesn't wipe out our hacked-in raw_data
        r.raw_data = {'@id': 'http://testserver/id/snake/python',
                      '@extant': False,
                      'eats': [anaconda.href]}
        r.save()
        link = Link.objects.get(source=r)
        self.assertEqual(link.extant, False)

    def testExtantLink(self):
        anaconda = Resource.objects.create(type_id='snake', identifier='anaconda')
        r = Resource.objects.create(type_id='snake', identifier='python')
        r.regenerate = mock.Mock() # So that saving doesn't wipe out our hacked-in raw_data
        r.raw_data = {'@id': 'http://testserver/id/snake/python',
                      '@extant': False,
                      'timelessF': [anaconda.href]}
        r.save()
        link = Link.objects.get(source=r)
        self.assertEqual(link.extant, True)

