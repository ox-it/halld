import copy
import datetime
import hashlib
import logging
from urllib.parse import urljoin

from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from jsonfield import JSONField
import jsonschema
import pytz
import rdflib
import ujson as json
import dateutil.parser
from stalefields.stalefields import StaleFieldsMixin

from . import signals, exceptions
from .registry import get_link_types, get_link_type
from .registry import ResourceTypeDefinition, get_resource_types, get_resource_type
from .registry import get_source_type
from .conf import is_spatial_backend
from .data import Data

if is_spatial_backend:
    from django.contrib.gis.db import models
    from django.contrib.gis.geos import Point
else:
    from django.db import models

logger = logging.getLogger(__name__)

MAX_HREF_LENGTH = 2048

def now():
    return pytz.utc.localize(datetime.datetime.utcnow())

def localize(dt):
    if isinstance(dt, str):
        dt = dateutil.parser.parse(dt)
    if not dt.tzinfo:
        dt = pytz.timezone(settings.TIME_ZONE).localize(dt)
    return dt

class ResourceType(models.Model):
    name = models.SlugField(primary_key=True)

    def __str__(self):
        return self.name

    class Meta:
        permissions = (
            ('instantiate_resourcetype', 'Can create a Resource of this ResourceType'),
        )

class Resource(models.Model, StaleFieldsMixin):
    href = models.CharField(max_length=MAX_HREF_LENGTH, primary_key=True)
    type = models.ForeignKey(ResourceType)
    identifier = models.SlugField()
    uri = models.CharField(max_length=MAX_HREF_LENGTH, db_index=True, blank=True)

    data = JSONField(default={}, blank=True)

    version = models.PositiveIntegerField(default=0)

    deleted = models.BooleanField(default=False)

    creator = models.ForeignKey(User)
    created = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(null=True, blank=True)

    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    extant = models.BooleanField(default=True)

    if is_spatial_backend:
        point = models.PointField(null=True, blank=True)
        geometry = models.GeometryField(null=True, blank=True)

    def get_etag(self):
        return hashlib.sha1("{}/{}".format(self.href, self.version).encode()).hexdigest()

    @property
    def cached_source_set(self):
        if not hasattr(self, '_cached_source_set'):
            self._cached_source_set = set(self.source_set.all())
        return self._cached_source_set
    @cached_source_set.setter
    def cached_source_set(self, value):
        self._cached_source_set = set(value)

    def collect_data(self):
        data = Data()
        data['href'] = self.get_absolute_url()
        data['@source'], data['identifier'], data['stableIdentifier'] = {}, {}, {}
        for source in self.cached_source_set:
            data['@source'][source.type_id] = copy.deepcopy(source.data)
        self.collect_identifiers(data)
        for inference in self.get_inferences():
            inference(self, data)
        for normalization in self.get_normalizations():
            normalization(self, data)
        data['identifier'].update(data['stableIdentifier'])

        if not self.get_type().allow_uri_override:
            data.pop('@id', None)
        if not data.get('@id'):
            data['@id'] = self.get_absolute_uri(data)
        del data['@source']
        return data

    def regenerate(self, cascade_set):
        data = self.collect_data()
        if data == self.data:
            return False
        old_data, self.data = self.data, data
        self.update_denormalized_fields()
        previous_linked_hrefs = self.get_link_hrefs(old_data)
        new_linked_hrefs = self.get_link_hrefs(data)
        cascade_set |= (previous_linked_hrefs | new_linked_hrefs)
        return True

    def save(self, *args, **kwargs):
        """
        Save, with a fair bit of cleverness. Takes the following optional kwargs:

        :param regeneration_path: A tuple of hrefs already regenerated. Will
            not try to regenerate them again.
        :param object_cache: An ObjectCache instance, which will be used to
            look up other Resource objects without hitting the database.
        :param cascade_set: A set, which if provided will stop this method
            cascading directly. Instead, resource hrefs to cascade to will be
            added to the set.
        :param regenerate: A boolean, which if false will stop this resource
            regenerating, on the assumption that it's been done already.
        """
        if not self.href:
            self.href = self.get_type().base_url + self.identifier

        object_cache = kwargs.pop('object_cache', None)
        regeneration_path = (self.href,) + kwargs.pop('regeneration_path', ())
        cascade = 'cascade_set' not in kwargs
        cascade_set = kwargs.pop('cascade_set', set())
        if kwargs.pop('regenerate', True):
            self.regenerate(cascade_set)

        if 'data' in self.stale_fields:
            self.created = self.created or now()
            self.modified = now()
            self.version += 1

            super(Resource, self).save(*args, **kwargs)
            self.update_links()
            self.update_identifiers()

            if cascade:
                cascade_set -= set(regeneration_path)
                if object_cache:
                    cascade_resources = object_cache.resource.get_many(cascade_set)
                else:
                    cascade_resources = Resource.objects.filter(href__in=cascade_set)
                for resource in cascade_resources:
                    resource.save(regeneration_path=regeneration_path,
                                  object_cache=object_cache)

            for date in [self.start_date, self.end_date]:
                if date and date > now():
                    signals.request_future_resource_generation.send(self, when=date)
                    break

        elif self.is_stale:
            super(Resource, self).save(*args, **kwargs)


    def update_denormalized_fields(self):
        self.uri = self.data['@id']
        self.deleted = bool(self.data.get('@deleted', False))
        self.extant = self.data.get('@extant', True)
        if '@startDate' in self.data:
            self.start_date = localize(self.data['@startDate'])
            if self.start_date > now():
                self.extant = False
        else:
            self.start_date = None
        if '@endDate' in self.data:
            self.end_date = localize(self.data['@endDate'])
            if self.end_date <= now():
                self.extant = False
        else:
            self.end_date = None
        self.data['@extant'] = self.extant

        if is_spatial_backend:
            point = self.data.get('@point')
            if isinstance(point, dict):
                try:
                    self.point = Point(point['lon'], point['lat'], point.get('ele'), srid=4326)
                except Exception:
                    logger.exception("Couldn't set point from dict: %r", point)
                    self.point = None
            elif isinstance(point, list):
                try:
                    self.point = Point(*point[:3], srid=4326)
                except Exception:
                    logger.exception("Couldn't set point from list: %r", point)
                    self.point = None
            else:
                self.point = None

    def get_inferences(self):
        return self.get_type().get_inferences()
    def get_normalizations(self):
        return self.get_type().get_normalizations()

    def get_type(self):
        return get_resource_type(self.type_id)

    def get_hal(self, user, object_cache, data=None, exclude_links=False):
        return self.get_type().get_hal(user, self, object_cache, data or self.data, exclude_links)

    def get_jsonld(self, user, data):
        jsonld = self.get_hal(user, data)
        jsonld.update(jsonld.pop('_links', {}))
        jsonld.update(jsonld.pop('_embedded', {}))
        return jsonld

    def get_link_hrefs(self, data):
        link_hrefs = set()
        for link_type in get_link_types().values():
            for link in data.get(link_type.name, ()):
                link_hrefs.add(link['href'])
        return link_hrefs

    def update_links(self):
        """
        Maintains Link objects based on self.data.
        """
        if not self.pk:
            super(Resource, self).save()

        link_data = set()
        for link_type in get_link_types().values():
            links = self.data.get(link_type.name, ())
            for link in links:
                if link.get('inbound'):
                    continue
                link_data.add((link['href'], link_type.name))

        self.link_set.all().delete()
        Link.objects.bulk_create([
            Link(source=self, target_href=href, type_id=link_name)
            for href, link_name in link_data
        ])

    def collect_identifiers(self, data):
        identifiers, stable_identifiers = {}, {}
        stable_identifiers.update(self.get_type().get_identifiers(self, data))
        stable_identifiers[self.type_id] = self.identifier
        for source in self.cached_source_set:
            if isinstance(source.data.get('identifier'), str):
                stable_identifiers['source:{}'.format(source.type_id)] = source.data['identifier']
        # Don't copy type name identifiers
        for resource_type in get_resource_types().values():
            if resource_type.name != self.type_id:
                stable_identifiers.pop(resource_type.name, None)
        data['stableIdentifier'].update(stable_identifiers)
        data['stableIdentifier']['uri'] = self.get_absolute_uri(data)

    def update_identifiers(self):
        Identifier.objects.filter(resource=self).delete()
        if self.extant:
            identifiers = self.data.get('identifier', {}).items()
        else:
            identifiers = self.data.get('stableIdentifier', {}).items()
        try:
            with transaction.atomic():
                Identifier.objects.bulk_create([
                    Identifier(resource=self, scheme=scheme, value=value)
                    for scheme, value in identifiers
                ])
        except IntegrityError:
            # One of them was duplicated, so find out which one
            for scheme, value in identifiers:
                try:
                    Identifier.objects.create(resource=self,
                                              scheme=scheme,
                                              value=value)
                except IntegrityError as e:
                    raise exceptions.DuplicatedIdentifier(scheme, value) from e

    def get_absolute_uri(self, data=None):
        data = data or self.data
        if data.get('@id'):
            return data['@id']
        identifiers = data.get('stableIdentifier', {})
        for uri_template in self.get_type().get_uri_templates():
            if uri_template is None:
                return reverse('halld:id', args=[self.type, self.identifier])
            try:
                return uri_template.format(**identifiers)
            except KeyError:
                pass
        raise AssertionError

    def get_absolute_url(self):
        return self.get_type().base_url + self.identifier

    def filter_data(self, user, data=None):
        data = data if data is not None else self.data
        if user.is_superuser:
            return data
        return self.get_type().filter_data(user, self, data)

    @classmethod
    def create(cls, creator, resource_type, identifier=None):
        if not isinstance(resource_type, ResourceTypeDefinition):
            resource_type = get_resource_type(resource_type)
        if not resource_type.user_can_create(creator):
            raise exceptions.Forbidden(creator)
        if not identifier:
            identifier = resource_type.generate_identifier()
        elif not resource_type.user_can_assign_identifier(creator, identifier):
            raise exceptions.CannotAssignIdentifier
        try:
            return Resource.objects.create(type_id=resource_type.name,
                                           identifier=identifier,
                                           creator=creator)
        except IntegrityError as e:
            raise exceptions.ResourceAlreadyExists(resource_type, identifier) from e

    def __str__(self):
        if 'title' in self.data:
            return '{} ("{}")'.format(self.href, self.data['title'])
        else:
            return self.href

    class Meta:
        index_together = [
            ['type', 'identifier'],
        ]
        ordering = ('type', 'identifier')

class SourceType(models.Model):
    name = models.SlugField(primary_key=True)

    def __str__(self):
        return self.name

class Source(models.Model, StaleFieldsMixin):
    href = models.CharField(max_length=2048, primary_key=True)
    resource = models.ForeignKey(Resource)
    type = models.ForeignKey(SourceType)

    author = models.ForeignKey(User, related_name='author_of_source')
    committer = models.ForeignKey(User, related_name='committer_of_source')

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    data = JSONField(default={}, blank=True)
    version = models.PositiveIntegerField(default=0)
    deleted = models.BooleanField(default=False)

    def get_etag(self):
        return hashlib.sha1("{}/{}".format(self.href, self.version).encode()).hexdigest()

    def filter_data(self, user, data=None):
        data = data if data is not None else self.data
        if user.is_superuser:
            return data
        return self.get_type().filter_data(user, self, data)

    def patch_acceptable(self, user, patch):
        return self.get_type().patch_acceptable(user, self, patch)

    def validate_data(self, data):
        return self.get_type().validate_data(self, data)
    
    def get_hal(self, user):
        return self.get_type().get_hal(self, self.filter_data(user))

    def get_absolute_url(self):
        return reverse('halld:source-detail', args=[self.resource.type, self.resource.identifier, self.type_id])

    def get_type(self):
        return get_source_type(self.type_id)

    def save(self, *args, **kwargs):
        created = not self.pk
        changed_values = self.get_changed_values()
        cascade_to_resource = kwargs.pop('cascade_to_resource', True)
        if not self.href:
            self.href = self.resource_id + '/source/' + self.type_id

        if 'deleted' in changed_values:
            if self.deleted:
                self.data = {}
                self.version += 1
                self.modified = now()
                super(Source, self).save(*args, **kwargs)
                signals.source_deleted.send(self)
                return
            elif not self.deleted:
                # Special-case resurrecting old Sources
                created = True
                changed_values['data'] = {}

        if created or 'data' in changed_values:
            self.version += 1
            self.created = self.created or now()
            self.modified = now()
            super(Source, self).save(*args, **kwargs)
            if created:
                signals.source_created.send(self)
            else:
                signals.source_changed.send(self, old_data=changed_values['data'])
            if cascade_to_resource:
                self.resource.save()
        elif self.is_stale:
            super(Source, self).save(*args, **kwargs)

    # Override so we can compare sources before we save and set the PK
    def __eq__(self, other):
        return isinstance(other, self.__class__) and \
            self.resource_id == other.resource_id and \
            self.type_id == other.type_id
    def __hash__(self):
        return hash((self.resource_id, self.type_id))

class LinkType(models.Model):
    name = models.SlugField(primary_key=True)

    def __str__(self):
        return self.name

class Link(models.Model):
    source = models.ForeignKey(Resource, db_index=True)
    target_href = models.CharField(max_length=MAX_HREF_LENGTH, db_index=True)
    type = models.ForeignKey(LinkType)

class Identifier(models.Model, StaleFieldsMixin):
    resource = models.ForeignKey(Resource, related_name='identifiers')
    scheme = models.CharField(max_length=1024)
    value = models.CharField(max_length=1024)
    
    class Meta:
        unique_together = (('scheme', 'value'),)
        index_together = (('scheme', 'value'),)

    def save(self, *args, **kwargs):
        changed_values = self.get_changed_values()
        super(Identifier, self).save(*args, **kwargs)
        if not self.pk:
            signals.identifier_added.send(self)
        elif 'value' in changed_values:
            signals.identifier_changed.send(self, old_value=changed_values['value'])

    def delete(self, *args, **kwargs):
        signals.identifier_removed.send(self)
        super(Identifier, self).delete(*args, **kwargs)

CHANGESET_STATE_CHOICES = (
    ('pending-approval', 'pending approval'),
    ('scheduled', 'scheduled'),
    ('performed', 'performed'),
    ('failed', 'failed'),
)

class Changeset(models.Model):
    author = models.ForeignKey(User, related_name='author_of_changeset')
    committer = models.ForeignKey(User, null=True, blank=True, related_name='committer_of_changeset')
    version = models.PositiveIntegerField(default=0)

    base_href = models.TextField()
    perform_at = models.DateTimeField(null=True, blank=True)
    performed = models.DateTimeField(null=True, blank=True)
    state = models.CharField(max_length=30, choices=CHANGESET_STATE_CHOICES) 

    data = JSONField()
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if 'performAt' in self.data:
            self.scheduled = dateutil.parser.parse(self.data['performAt'])
        else:
            self.scheduled = None
        self.description = self.data.get('description', '')
        self.version += 1
        return super(Changeset, self).save(*args, **kwargs)
    
    @transaction.atomic
    def perform(self, multiple=False, object_cache=None):
        from . import changeset # to avoid a circular import

        if self.state in ('pending-approval', 'performed', 'failed'):
            return
        try:
            jsonschema.validate(self.data, changeset.schema)
        except jsonschema.ValidationError as e:
            raise exceptions.SchemaValidationError(e)
        if self.pk:
            try:
                Changeset.objects.select_for_update().get(pk=self.pk, version=self.version)
            except Changeset.DoesNotExist as e:
                raise exceptions.ChangesetConflict() from e
        updater = changeset.SourceUpdater(self.base_href, self.author, self.committer, multiple=multiple,
                                          object_cache=object_cache)
        try:
            with transaction.atomic():
                updater.perform_updates(self.data)
        except Exception:
            self.state = 'failed'
            self.performed = now()
            self.save()
            raise
        else:
            self.state = 'performed'
            self.performed = now()
            self.save()
