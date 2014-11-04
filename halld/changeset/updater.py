import abc
import collections
import contextlib
import functools
import re
from urllib.parse import urljoin

from django.db import transaction
import jsonschema

from .schema import schema
from . import methods
from ..registry import get_source_types, get_source_type
from ..util.resource_cache import ResourceCache
from .. import exceptions

class SourceUpdater(object):
    schema = schema
    methods = {
        'PUT': methods.PutUpdate,
        'DELETE': methods.DeleteUpdate,
        'PATCH': methods.PatchUpdate,
        'MOVE': methods.MoveUpdate,
    }

    source_href_re = re.compile(r'^(?P<source_href>(?P<resource_href>(?P<resource_type_href>.+)/(?P<identifier>[a-z\-\d]+))/source/(?P<source_type>[a-z\i\d:\-]+))$')


    def __init__(self, base_href, author, committer=None, multiple=False,
                 resource_cache=None):
        self.base_href = base_href
        self.author = author
        self.committer = committer or author
        self.multiple = multiple
        self.resource_cache = resource_cache or ResourceCache(self.committer)

    @contextlib.contextmanager
    def save_wrapper(self, errors, error_handling, with_transaction=None):
        try:
            if with_transaction != True and (with_transaction == False or error_handling == 'fail-first'):
                yield
            else:
                with transaction.atomic():
                    yield
        except exceptions.HALLDException as error:
            if not self.multiple:
                raise
            errors.append(error)
            if error_handling == 'fail-first':
                raise exceptions.MultipleErrors(errors)

    def perform_updates(self, data):
        """
        Updates sources and fires events.
        """
        from ..models import Resource, Source

        updates = data['updates']
        error_handling = data.get('error-handling', "fail-first")
        errors = []
        save_wrapper = functools.partial(self.save_wrapper, errors, error_handling)

        bad_hrefs = set()
        for update in updates:
            if 'href' in update:
                update['href'] = urljoin(self.base_href, update['href'])
                match = self.source_href_re.match(update['href'])
                if not match:
                    bad_hrefs.add(update['href'])
                update['resourceHref'] = match.group('resource_href') 
                update['sourceType'] = match.group('source_type')
            else:
                update['resourceHref'] = urljoin(self.base_href, update['resourceHref'])
                update['href'] = '{}/source/{}'.format(update['resourceHref'], update['sourceType'])
        if bad_hrefs:
            raise exceptions.BadHrefs(bad_hrefs)

        resource_hrefs = set(update['resourceHref'] for update in updates)
        source_types = set(update['sourceType'] for update in updates)

        missing_source_types = source_types - set(get_source_types())
        if missing_source_types:
            raise exceptions.NoSuchSourceType(missing_source_types)

        resources = {r.href: r for r in Resource.objects.filter(href__in=resource_hrefs)}
        missing_hrefs = resource_hrefs - set(resources)
        if missing_hrefs:
            raise exceptions.SourceDataWithoutResource(missing_hrefs)

        source_hrefs = set(update['href'] for update in updates)
        sources = {s.href: s for s in Source.objects.select_for_update().filter(href__in=source_hrefs)}

        results = collections.defaultdict(set)
        modified = set()
        for update in updates:
            try:
                method = self.methods[update['method']].from_json(update)
            except KeyError as e:
                raise exceptions.MethodNotAllowed(update['method'], bad_request=True) from e
            try:
                source = sources[update['href']]
            except KeyError as e:
                # No need to create sources that would be deleted anyway
                if method.will_delete:
                    continue
                if method.require_source_exists:
                    raise exceptions.NoSuchSource(update['href']) from e
                resource = resources[update['resourceHref']]
                if update['sourceType'] not in resource.get_type().source_types:
                    with save_wrapper(with_transaction=False):
                        raise exceptions.IncompatibleSourceType(resource.type_id,
                                                                update['sourceType']) from e
                    continue
                source = Source(resource=resource,
                                type_id=update['sourceType'])
                sources[update['href']] = source
            result = method(self.author, self.committer, source)
            if result:
                source.author = self.author
                source.committer = self.committer
                modified.add(source)
            results[result].add(source)

        for source in modified:
            with save_wrapper():
                source.save(cascade_to_resource=False)

        modified_resources = set(source.resource for source in modified)
        for modified_resource in modified_resources:
            with save_wrapper():
                modified_resource.save()

        if errors:
            if self.error_handling == 'ignore':
                raise exceptions.MultipleErrors(errors)
            else:
                return exceptions.MultipleErrors(errors)
