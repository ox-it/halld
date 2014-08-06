import datetime

from django.contrib.auth.models import User
from django.test import TestCase
import mock

from ..models import Resource, Identifier, Link

class ExtantTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='superuser',
                                                  email='superuser@example.com',
                                                  password='secret')

    def tearDown(self):
        Resource.objects.all().delete()
        User.objects.all().delete()

    def testExtantFalse(self):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.user)
        r.data = {'@id': 'http://testserver/id/snake/python',
                  '@extant': False}
        r.update_denormalized_fields()
        self.assertEqual(r.extant, False)

    def testNotYetCurrent(self):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.user)
        r.data = {'@id': 'http://testserver/id/snake/python',
                  # This resource starts existing two days from now.
                  '@startDate': (datetime.date.today() + datetime.timedelta(2)).isoformat()}
        r.update_denormalized_fields()
        self.assertEqual(r.extant, False)

    def testBeenAndGone(self):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.user)
        r.data = {'@id': 'http://testserver/id/snake/python',
                  # This resource stopped existing two days ago.
                  '@endDate': (datetime.date.today() - datetime.timedelta(2)).isoformat()}
        r.update_denormalized_fields()
        self.assertEqual(r.extant, False)

    @mock.patch('halld.signals.request_future_resource_generation')
    def testFutureExistenceSignal(self, request_future_resource_generation):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.user)
        self.assertFalse(request_future_resource_generation.called)
        r.generate_data = mock.Mock()
        r.generate_data.return_value = {'@id': 'http://testserver/id/snake/python',
                                        # This resource starts existing two days from now.
                                        '@startDate': (datetime.date.today() + datetime.timedelta(2)).isoformat()}
        r.save()
        self.assertEqual(r.generate_data.call_count, 1)
        request_future_resource_generation.send.assert_called_once_with(r, when=r.start_date)

    def testNoIdentifiersForNonExtantResources(self):
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.user)
        r.generate_data = mock.Mock()
        r.generate_data.return_value = {'@id': 'http://testserver/id/snake/python',
                                        '@extant': False,
                                        'identifier': {'foo': 'bar'}}
        r.save()
        self.assertEqual(Identifier.objects.filter(resource=r,
                                                   scheme='foo',
                                                   value='bar').count(), 0)

    def testNonExtantLink(self):
        anaconda = Resource.objects.create(type_id='snake', identifier='anaconda', creator=self.user)
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.user)
        r.generate_data = mock.Mock()
        r.generate_data.return_value = {'@id': 'http://testserver/id/snake/python',
                                        '@extant': False,
                                        'eats': [{'href': anaconda.href}]}
        r.save()
        self.assertFalse(r.extant)
        link = Link.objects.get(source=r, type_id='eats')
        self.assertEqual(link.extant, False)
        link = Link.objects.get(source=r, type_id='eatenBy')
        self.assertEqual(link.extant, False)

    def testExtantLink(self):
        anaconda = Resource.objects.create(type_id='snake', identifier='anaconda', creator=self.user)
        r = Resource.objects.create(type_id='snake', identifier='python', creator=self.user)
        r.generate_data = mock.Mock()
        r.generate_data.return_value = {'@id': 'http://testserver/id/snake/python',
                                        '@extant': False,
                                        'timelessF': [{'href': anaconda.href}]}
        r.save()
        link = Link.objects.get(source=r, type_id='timelessF')
        self.assertEqual(link.extant, True)
        link = Link.objects.get(source=r, type_id='timelessR')
        self.assertEqual(link.extant, True)

