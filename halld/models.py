import copy
import datetime
import hashlib
import logging
from urllib.parse import urljoin

from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.db import IntegrityError
from jsonfield import JSONField
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

    def generate_data(self):
        data = Data()
        data['href'] = self.get_absolute_url()
        data['@source'], data['identifier'] = {}, {}
        for source in self.source_set.all():
            data['@source'][source.type_id] = copy.deepcopy(source.data)
        self.collect_identifiers(data)
        for inference in self.get_inferences():
            inference(self, data)
        for normalization in self.get_normalizations():
            normalization(self, data)

        if not self.get_type().allow_uri_override:
            data.pop('@id', None)
        if not data.get('@id'):
            data['@id'] = self.get_absolute_uri(data)
        del data['@source']

        return data

    def save(self, *args, **kwargs):
        created = not self.pk
        if not self.href:
            self.href = self.get_type().base_url + self.identifier
        if created:
            super(Resource, self).save(*args, **kwargs)
        if kwargs.pop('regenerate', True) is not False:
            data = self.generate_data()
        regenerated = {self.href} | kwargs.pop('regenerated', set())

        old_data = self.data
        if data != old_data:
            self.data = data

            previous_linked_hrefs = self.get_link_hrefs(old_data)
            new_linked_hrefs = self.get_link_hrefs(data)

            cascade_to = (previous_linked_hrefs | new_linked_hrefs) - regenerated
            regenerated |= cascade_to

            self.update_denormalized_fields()
            self.update_links()
            self.update_identifiers()

            self.created = self.created or now()
            self.modified = now()
            self.version += 1

            super(Resource, self).save()
            if created:
                signals.resource_created.send(self)
            else:
                signals.resource_changed.send(self, old_data=old_data)

            for resource in Resource.objects.filter(href__in=cascade_to):
                resource.save(regenerated=regenerated)
        elif self.is_stale:
            super(Resource, self).save()

        for date in [self.start_date, self.end_date]:
            if date and date > now():
                signals.request_future_resource_generation.send(self, when=date)
                break

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

    def get_hal(self, user, data=None):
        return self.get_type().get_hal(user, self, data or self.data)

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
        hrefs = set()
        for link_type in get_link_types().values():
            links = self.data.get(link_type.name, ())
            for link in links:
                if link.get('inbound'):
                    continue
                link_data.add((self.href,
                               link['href'],
                               link_type.name))
                hrefs.add(link['href'])
        link_data |= set((l[1], l[0], get_link_type(l[2]).inverse_name) for l in link_data)

        targets = {r.href: r for r in Resource.objects.filter(href__in=hrefs)}
        targets[self.href] = self

        links = list(Link.objects.filter(source=self).select_related('active', 'passive'))
        for link in links:
            lid = link.active_href, link.passive_href, link.type_id
            if lid in link_data:
                extant = get_link_type(link.type_id).timeless or ((not link.active_id or link.active.extant)
                                                              and (not link.passive_id or link.passive.extant))
                if extant != link.extant:
                    link.extant = extant
                    link.save()
                link_data.remove(lid)
            else:
                link.delete()
        for active_href, passive_href, link_name in link_data:
            link_type = get_link_type(link_name)
            active = targets.get(active_href)
            passive = targets.get(passive_href)
            target = active if passive_href == self.href else passive
            if link_type.strict:
                if not active:
                    raise exceptions.LinkTargetDoesNotExist(get_link_type(link_name), active_href)
                if not passive:
                    raise exceptions.LinkTargetDoesNotExist(get_link_type(link_name), passive_href)
            links.append(Link.objects.create(source=self,
                                             target=target,
                                             active_href=active_href,
                                             passive_href=passive_href,
                                             active=active,
                                             passive=passive,
                                             type_id=link_name,
                                             extant=link_type.timeless or (self.extant
                                                                       and (target is None or target.extant))))

        targets.pop(self.href)

    def collect_identifiers(self, data):
        identifiers = {}
        identifiers.update(self.get_type().get_identifiers(self, data))
        identifiers[self.type_id] = self.identifier
        for source in self.source_set.all():
            if isinstance(source.data.get('identifier'), str):
                identifiers['source:{}'.format(source.type_id)] = source.data['identifier']
        # Don't copy type name identifiers
        for resource_type in get_resource_types().values():
            if resource_type.name != self.type_id:
                identifiers.pop(resource_type.name, None)
        data['identifier'].update(identifiers)
        data['identifier']['uri'] = self.get_absolute_uri(data)

    def update_identifiers(self):
        if self.extant:
            identifiers = self.data.get('identifier', {}).copy()
        else:
            identifiers = {}
        for current in Identifier.objects.filter(resource=self):
            if current.scheme not in identifiers:
                current.delete()
                continue
            elif current.value != identifiers[current.scheme]:
                current.value = identifiers[current.scheme]
                try:
                    current.save()
                except IntegrityError:
                    raise exceptions.DuplicatedIdentifier(current.scheme, current.value)
            del identifiers[current.scheme]
        for scheme, value in identifiers.items():
            try:
                Identifier.objects.create(resource=self,
                                          scheme=scheme,
                                          value=value)
            except IntegrityError:
                raise exceptions.DuplicatedIdentifier(scheme, value)

    def get_absolute_uri(self, data=None):
        data = data or self.data
        if data.get('@id'):
            return data['@id']
        identifiers = data.get('identifier', {})
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
            raise exceptions.ResourceAlreadyExists(resource_type, identifier)

    def __str__(self):
        if 'title' in self.data:
            return '{} ("{}")'.format(self.href, self.data['title'])
        else:
            return self.href

    class Meta:
        index_together = [
            ['type', 'identifier'],
        ]

class SourceType(models.Model):
    name = models.SlugField(primary_key=True)

    def __str__(self):
        return self.name

class Source(models.Model, StaleFieldsMixin):
    href = models.CharField(max_length=2048, primary_key=True)
    resource = models.ForeignKey(Resource)
    type = models.ForeignKey(SourceType)

    author = models.ForeignKey(User, related_name='author_of')
    committer = models.ForeignKey(User, related_name='committer_of')

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
    source = models.ForeignKey(Resource, related_name='link_source')
    target = models.ForeignKey(Resource, related_name='target', null=True, blank=True)
    active_href = models.CharField(max_length=MAX_HREF_LENGTH)
    passive_href = models.CharField(max_length=MAX_HREF_LENGTH)
    active = models.ForeignKey(Resource, related_name='link_active', null=True, blank=True)
    passive = models.ForeignKey(Resource, related_name='link_passive', null=True, blank=True)
    type = models.ForeignKey(LinkType)
    extant = models.BooleanField(default=True)

class Identifier(models.Model, StaleFieldsMixin):
    resource = models.ForeignKey(Resource, related_name='identifiers')
    scheme = models.SlugField()
    value = models.SlugField()
    
    class Meta:
        unique_together = (('scheme', 'value'),)

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
