import abc
import collections
import re
from urllib.parse import urljoin

import jsonschema

from .schema import schema
from . import methods
from ..registry import get_source_types, get_source_type
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


    def __init__(self, base_href, author, committer=None):
        self.base_href = base_href
        self.author = author
        self.committer = committer or author

    def perform_updates(self, data):
        """
        Updates sources and fires events.
        """
        from ..models import Resource, Source

        updates = data['updates']

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
            except KeyError:
                raise exceptions.MethodNotAllowed(update['method'], bad_request=True)
            try:
                source = sources[update['href']]
            except KeyError:
                # No need to create sources that would be deleted anyway
                if method.will_delete:
                    continue
                if method.require_source_exists:
                    raise exceptions.NoSuchSource(update['href'])
                source = Source(resource=resources[update['resourceHref']],
                                type_id=update['sourceType'])
                sources[update['href']] = source
            result = method(self.author, self.committer, source)
            if result:
                source.author = self.author
                source.committer = self.committer
                modified.add(source)
            results[result].add(source)

        for source in modified:
            source.save(cascade_to_resource=False)

        modified_resources = set(source.resource for source in modified)
        for modified_resource in modified_resources:
            modified_resource.save()
