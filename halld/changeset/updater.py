import abc
import collections
import contextlib
import functools
import logging
import re
from urllib.parse import urljoin

from django.db import IntegrityError, transaction
import jsonschema

from .schema import schema
from . import methods
from ..util.cache import ObjectCache
from .. import exceptions
from .. import models
from .. import get_halld_config

logger = logging.getLogger(__name__)

class IdentifierCache(collections.defaultdict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reverse = collections.defaultdict(set)

    def __missing__(self, key):
        resource = models.Identifier.objects.select_related('resource').get(scheme=key[0], value=key[1]).resource.href
        self[key] = resource
        return resource
    def __setitem__(self, key, value):
        self.reverse[value].add(key)
        super().__setitem__(key, value)
    def __delitem__(self, key):
        self.reverse[self[key]].remove(key)
        super().__delitem__(key)

class SourceUpdater(object):
    schema = schema
    methods = {
        'PUT': methods.PutUpdate,
        'DELETE': methods.DeleteUpdate,
        'PATCH': methods.PatchUpdate,
        'MOVE': methods.MoveUpdate,
    }
    max_cascades = 10

    source_href_re = re.compile(r'^(?P<source_href>(?P<resource_href>(?P<resource_type_href>.+)/(?P<identifier>[a-z\-\d]+))/source/(?P<source_type>[a-z\i\d:\-]+))$')


    def __init__(self, base_href, author, committer=None, multiple=False,
                 object_cache=None):
        self.base_href = base_href
        self.author = author
        self.committer = committer or author
        self.multiple = multiple
        self.object_cache = object_cache or ObjectCache(self.committer)

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
        from ..models import Source

        if data.get('regenerateAll') and not self.committer.is_superuser:
            raise exceptions.CantRegenerateAll()
        elif data.get('regenerateAll'):
            logger.info("Regenerating all for user %s", self.committer.username)

        updates = data.get('updates', [])
        logger.info("Performing %d updates for user %s", len(updates), self.committer.username)
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

        missing_source_types = source_types - set(get_halld_config().source_types)
        if missing_source_types:
            raise exceptions.NoSuchSourceType(missing_source_types)

        if data.get('regenerateAll'):
            resources = list(models.Resource.objects.all())
            self.object_cache.resource.add_many(resources)
        else:
            resources = filter(None, self.object_cache.resource.get_many(resource_hrefs, ignore_missing=True))
        resources = {r.href: r for r in resources}
        missing_hrefs = resource_hrefs - set(resources)
        if missing_hrefs:
            raise exceptions.SourceDataWithoutResource(missing_hrefs)

        source_hrefs = set(update['href'] for update in updates)
        sources = {s.href: s for s in Source.objects.select_for_update().filter(href__in=source_hrefs)}

        results = collections.defaultdict(set)
        modified = set()
        for i, update in enumerate(updates, 1):
            if i % 100 == 0:
                logger.debug("Updating source %d of %d for user %s",
                             i, len(updates), self.committer.username)
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

        for i, source in enumerate(modified, 1):
            if i % 100 == 0:
                logger.debug("Saving source %d of %d for user %s",
                             i, len(modified), self.committer.username)
            with save_wrapper():
                source.save(cascade_to_resource=False)

        save_set = set()

        sources_by_resource = collections.defaultdict(set)
        for source in Source.objects.filter(resource__in=set(resources)):
            sources_by_resource[source.resource_id].add(source)
        for href, sources in sources_by_resource.items():
            resources[href].cached_source_set = sources

        identifier_cache = IdentifierCache()
        resources_to_save = set(resources.values())
        for i in range(1, self.max_cascades + 1):
            logger.debug("Cascade %d: %d resources to save",
                             i, len(resources_to_save))
            cascade_set = set()
            changed = 0

            inbound_links = collections.defaultdict(list)
            for link in models.Link.objects.filter(target_href__in=[r.href for r in resources_to_save]):
                inbound_links[link.target_href].append(link)

            for j, resource in enumerate(resources_to_save, 1):
                if j % 100 == 0:
                    logger.debug("Regenerating resource %d of %d for user %s (%d changed, %d cascades)",
                                 j, len(resources_to_save), self.committer.username,
                                 changed,
                                 len(cascade_set))
                if resource.regenerate(cascade_set,
                                       self.object_cache,
                                       prefetched_data={'inbound_links': inbound_links[resource.href],
                                                        'identifiers': identifier_cache}):
                    identifiers_to_drop = set(identifier_cache.reverse[resource.href])
                    changed += 1
                    for k in identifiers_to_drop:
                        del identifier_cache[k]
                    for k, v in resource.identifier_data:
                        identifier_cache[(k, v)] = resource.href
                    resource.update_links()
                    save_set.add(resource)
            if not cascade_set:
                break
            resources_to_save = set(self.object_cache.resource.get_many(cascade_set))
        else:
            logger.warning("Still %d resources to cascade to after %d cascades",
                           len(cascade_set), self.max_cascades)

        for i, resource in enumerate(save_set, 1):
            if i % 100 == 0:
                logger.debug("Saving resource %d of %d for user %s",
                             i, len(resources), self.committer.username)
            with save_wrapper():
                resource.save(regenerate=False,
                              update_links=False,
                              update_identifiers=False,
                              force_update=True,
                              object_cache=self.object_cache)
        with save_wrapper():
            models.Identifier.objects.filter(resource_id__in=[r.href for r in save_set]).delete()
            try:
                models.Identifier.objects.bulk_create(
                    models.Identifier(resource=resource, scheme=scheme, value=value)
                    for resource in save_set
                    for scheme, value in resource.identifier_data)
            except IntegrityError as e:
                match = re.search(r'DETAIL:  Key \(scheme, value\)=\(([^,]+), ([^)])+\) already exists.', e.args[0])
                if match:
                    raise exceptions.DuplicatedIdentifier(match.group(1), match.group(2)) from e
                else:
                    raise exceptions.DuplicatedIdentifier() from e

        if errors:
            if self.error_handling == 'ignore':
                raise exceptions.MultipleErrors(errors)
            else:
                return exceptions.MultipleErrors(errors)
