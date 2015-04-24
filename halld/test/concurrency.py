import functools
import http.client
import json
import threading
import unittest

from django.test import skipUnlessDBFeature
from rest_framework.test import force_authenticate

from ..models import Resource
from .base import TestCase

class ExceptionInThread(Exception):
    pass

class ExceptionalThread(threading.Thread):
    def run(self):
        self._exc = None
        try:
            super().run()
        except Exception as e:
            self._exc = e
        finally:
            from django.db import connection
            connection.close()

    def join(self):
        super().join()
        if self._exc:
            raise ExceptionInThread from self._exc

def run_in_thread(func=None, join=False, args=(), kwargs={}):
    if not func:
        return functools.partial(run_in_thread, join=join, args=args, kwargs=kwargs)
    thread = ExceptionalThread(target=func, args=args, kwargs=kwargs)
    thread.start()
    if join:
        thread.join()
    return thread

class ConcurrencyTestCase(TestCase):
    @skipUnlessDBFeature('atomic_transactions')
    def testParallelUpdate(self):
        identifier = None
        source_types = ('science', 'mythology')

        @run_in_thread(join=True)
        def create_resource():
            nonlocal identifier
            _, identifier = self.create_resource()

        def update_source(source_type):
            data = {
                'updates': [{
                    'resourceHref': '/snake/' + identifier,
                    'sourceType': source_type,
                    'method': 'PUT',
                    'data': {source_type: 'hello'},
                }]
            }
            request = self.factory.post('/changeset',
                                        data=json.dumps(data),
                                        content_type='application/json')
            force_authenticate(request, self.superuser)
            response = self.changeset_list_view(request)
            self.assertEqual(response.status_code, http.client.NO_CONTENT)
        
        threads = []
        for source_type in source_types:
            threads.append(run_in_thread(update_source, args=(source_type,)))
        for thread in threads:
            thread.join()
        
        resource = Resource.objects.get()
        for source_type in source_types:
            self.assertEqual(resource.data.get(source_type), 'hello')

    @unittest.expectedFailure
    @skipUnlessDBFeature('atomic_transactions')
    def testMutualCascade(self):
        identifier_a, identifier_b = None, None

        @run_in_thread(join=True)
        def create_resources():
            nonlocal identifier_a, identifier_b
            _, identifier_a = self.create_resource()
            _, identifier_b = self.create_resource()
        
        def update_source(identifier, target_identifier):
            data = {
                'updates': [{
                    'resourceHref': '/snake/' + identifier,
                    'sourceType': 'science',
                    'method': 'PUT',
                    'data': {'eats': '/snake/' + target_identifier},
                }]
            }
            request = self.factory.post('/changeset',
                                        data=json.dumps(data),
                                        content_type='application/json')
            force_authenticate(request, self.superuser)
            response = self.changeset_list_view(request)
            self.assertEqual(response.status_code, http.client.NO_CONTENT)

        threads = []
        for identifier, target_identifier in ((identifier_a, identifier_b), (identifier_b, identifier_a)):
            threads.append(run_in_thread(update_source, args=(identifier, target_identifier)))
        for thread in threads:
            thread.join()

        for resource in Resource.objects.all():
            self.assertIn('eats', resource.data)
            self.assertIn('eatenBy', resource.data)
