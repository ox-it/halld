import abc
import collections
from urllib.parse import urljoin

from django.core.exceptions import PermissionDenied
import jsonschema

from .schema import schema
from . import methods
from ..models import Resource, Source
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
    
    def __init__(self, base_href, author, committer=None):
        self.base_href = base_href
        self.author = author
        self.committer = committer or author

    def perform_updates(self, updates):
        """
        Updates sources and fires events.
        """
        try:
            jsonschema.validate(updates, self.schema)
        except jsonschema.SchemaError as e:
            raise exceptions.SchemaValidationError(e)
    
        hrefs = set(urljoin(self.base_href, update['href']) for update in updates)
        source_types = set(update['sourceType'] for update in updates)
        
        missing_source_types = set(get_source_types()) - source_types
        if missing_source_types:
            raise exceptions.NoSuchSourceType(missing_source_types)
    
        resources = {r.href: r for r in Resource.objects.filter(href__in=hrefs)}
        missing_hrefs = set(resources) - hrefs
        if missing_hrefs:
            raise exceptions.NoSuchResource(missing_hrefs)
    
        for update in updates:
            update['sourceHref'] = urljoin(self.base_href,
                                           update['resourceHref'] + '/source/' + update['source'])
        source_hrefs = set(update['sourceHref'] for update in updates)
        sources = {s.href: s for s in Source.objects.select_for_update().filter(href__in=source_hrefs)}

        results = collections.defaultdict(set)
        modified = set()
        for update in updates:
            try:
                method = self.methods[update['method']](update)
            except KeyError:
                raise exceptions.MethodNotAllowed(update['method'], bad_request=True)
            try:
                source = sources[update['sourceHref']]
            except KeyError:
                if method.require_source_exists:
                    raise exceptions.NoSuchSource(update['sourceHref'])
                source = Source(resource_id=update['href'],
                                type_id=update['sourceType'])
                sources[source.href] = source
            result = method(self.author, self.committer, source)
            if result:
                source.author = self.author
                source.committer = self.committer
                source.save(cascade_to_resource=False)
                modified.add(source)
            results[result].add(source)

        modified_resources = set(source.resoruce for source in modified)
        for modified_resource in modified_resources:
            modified_resource.save()
