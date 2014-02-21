from collections import defaultdict
import copy
import datetime
import itertools
import logging

from django.conf import settings
from django.db.models import Q
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from jsonfield import JSONField
import rdflib
import ujson as json
import dateutil.parser
from stalefields.stalefields import StaleFieldsMixin

from . import signals
from .links import get_links
from .types import get_types

BASE_JSONLD_CONTEXT = getattr(settings, 'BASE_JSONLD_CONTEXT', {}) 

logger = logging.getLogger(__name__)

class Resource(models.Model, StaleFieldsMixin):
    rid = models.CharField(max_length=128, db_index=True, blank=True)
    type = models.SlugField()
    identifier = models.SlugField()
    uri = models.CharField(max_length=1024, db_index=True, blank=True)

    raw_data = JSONField(default={}, blank=True)
    data = JSONField(default={}, blank=True)

    version = models.PositiveIntegerField(default=0)

    deleted = models.BooleanField(default=False)
    extant = models.BooleanField(default=True)

    created = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(null=True, blank=True)

    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    point = models.PointField(null=True, blank=True)
    geometry = models.GeometryField(null=True, blank=True)
    
    def regenerate(self):
        raw_data = {'@source': {},
                    'href': self.get_absolute_url()}
        for source_data in self.sourcedata_set.all():
            raw_data['@source'][source_data.source_id] = copy.deepcopy(source_data.data)
        inferences = self.get_inferences()
        for inference in inferences:
            inference(self, raw_data)
        
        if not self.get_type().allow_uri_override:
            raw_data.pop('@id', None)
        if not raw_data.get('@id'):
            raw_data['@id'] = self.get_absolute_uri(raw_data)
        del raw_data['@source']

        self.raw_data = copy.deepcopy(raw_data)

    def save(self, *args, **kwargs):
        has_pk = self.pk is not None
        self.rid = '{}/{}'.format(self.type, self.identifier)
        if kwargs.pop('regenerate') is not False:
            self.regenerate()
        dirty_fields = self.get_stale_fields()
        if 'raw_data' in dirty_fields:
            cascade_to = self.update_data()
            regenerated = kwargs.pop('regenerated', set())
            cascade_to -= regenerated

        dirty_fields = self.get_stale_fields()
        if 'data' in dirty_fields:
            self.created = self.created or datetime.datetime.utcnow()
            self.modified = datetime.datetime.utcnow()
            self.version += 1
            super(Resource, self).save(*args, **kwargs)
            if has_pk:
                signals.resource_updated(self, dirty_fields['data'])
            else:
                signals.resource_created(self)

            for resource in cascade_to:
                resource.save(regenerated=regenerated)
        elif self.is_stale():
            super(Resource, self).save(*args, **kwargs)

    def update_data(self, regenerated):
        cascade_to = set()
        cascade_to.update(l.target for l in Link.objects.filter(source=self).select_related('target'))
        cascade_to.update(self.update_links(self.raw_data))
        cascade_to -= regenerated
        
        self.update_identifiers(self.raw_data)

        data = copy.deepcopy(self.raw_data)
        for link in get_links().values():
            data.pop(link.name, None)
        data['meta'] = {'created': self.created,
                        'modified': self.modified,
                        'version': self.version}
        self.data = data

        return cascade_to

    def update_denormalised_fields(self):
        self.uri = self.raw_data['@id']
        self.deleted = bool(self.raw_data.get('@deleted', False))
        if '@startDate' in self.raw_data:
            self.start_date = dateutil.parser.parse(self.raw_data['@endDate'])
        else:
            self.start_date = None
        if '@endDate' in self.raw_data:
            self.end_date = dateutil.parser.parse(self.raw_data['@endDate'])
        else:
            self.end_date = None

        point = self.raw_data.get('@point')
        if isinstance(point, dict):
            try:
                self.point = Point(point['lat'], point['lon'], point.get('alt'), srid=4326)
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

    def get_type(self):
        return get_types()[self.type]

    def get_hal(self, user, data=None):
        return self.get_type().get_hal(user, self, data or self.data)

    def get_jsonld(self, user, data):
        jsonld = self.get_hal(user, data)
        jsonld.update(jsonld.pop('_links', {}))
        jsonld.update(jsonld.pop('_embedded', {}))
        return jsonld

    def update_links(self, data):
        if not self.pk:
            self.save()

        targets = set()
        link_data = set()
        for link in get_links().values():
            rids = data.get(link.name, [])
            if not isinstance(rids, list):
                rids = [rids]
            targets.update(rids)
            for rid in rids:
                if link.inverted:
                    link_data.add((rid, link.inverse_name, True))
                else:
                    link_data.add((rid, link.name, False))

        targets = {r.rid: r for r in Resource.objects.filter(rid__in=targets)}

        links = list(Link.objects.filter(source=self).select_related('target'))
        for link in links:
            lid = link.target.rid, link.link_name, link.inverted
            if lid in link_data:
                link_data.remove(lid)
            else:
                link.delete()
        for rid, link_name, inverted in link_data:
            target = targets[rid]
            links.append(Link.objects.create(source=self,
                                             target=target,
                                             link_name=link_name,
                                             active=target if inverted else self,
                                             passive=self if inverted else target,
                                             inverted=inverted))
        return [l.target for l in links]

    def update_identifiers(self, data):
        identifiers = dict(data.get('identifier', {}))
        for current in Identifier.objects.filter(resource=self):
            if current.scheme not in identifiers:
                current.delete()
                continue
            elif current.value != identifiers[current.scheme]:
                current.value = identifiers[current.scheme]
                current.save()
            del identifiers[current.scheme]
        for scheme, value in identifiers.items():
            Identifier.objects.create(resource=self,
                                      scheme=scheme,
                                      value=value)

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
        return reverse('halld:resource', args=[self.type, self.identifier])

    def filter_data(self, user, data=None):
        data = data if data is not None else self.data
        return data
    
    def __str__(self):
        if 'label' in self.data:
            return '{} ("{}")'.format(self.rid, self.data['label'])
        else:
            return self.rid

    class Meta:
        index_together = [
            ['type', 'identifier'],
        ]

class Source(models.Model):
    slug = models.SlugField(primary_key=True)

class SourceData(models.Model, StaleFieldsMixin):
    resource = models.ForeignKey(Resource)
    source = models.ForeignKey(Source)

    author = models.ForeignKey(User, related_name='author_of')
    committer = models.ForeignKey(User, related_name='committer_of')

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    data = JSONField(default={}, blank=True)
    version = models.PositiveIntegerField(default=1)
    deleted = models.BooleanField(default=False)

    def get_etag(self):
        return "{}/{}/{}/{}".format(self.resource.type,
                                    self.resource.identifier,
                                    self.source_id,
                                    self.version)

    def filter_data(self, user, data=None):
        data = data if data is not None else self.data
        return data

    def patch_acceptable(self, user, patch):
        return True

    def get_absolute_url(self):
        return reverse('halld:source-detail', args=[self.resource.type, self.resource.identifier, self.source_id])

    def save(self, *args, **kwargs):
        stale_fields = self.get_stale_fields()
        if 'data' in stale_fields:
            self.version += 1
            super(SourceData, self).save()
            if not self.pk:
                signals.sourcedata_created.send(self)
            else:
                signals.sourcedata_updated.send(self, old_data=stale_fields['data'])
            self.resource.refresh()
        elif self.is_stale():
            super(SourceData, self).save()

class Link(models.Model):
    source = models.ForeignKey(Resource, related_name='link_source')
    target = models.ForeignKey(Resource, related_name='link_target')
    active = models.ForeignKey(Resource, related_name='link_active')
    passive = models.ForeignKey(Resource, related_name='link_passive')
    link_name = models.SlugField()
    inverted = models.BooleanField()

class Identifier(models.Model, StaleFieldsMixin):
    resource = models.ForeignKey(Resource, related_name='identifiers')
    scheme = models.SlugField()
    value = models.SlugField()

    def save(self, *args, **kwargs):
        dirty_fields = self.get_stale_fields()
        super(Identifier, self).save(*args, **kwargs)
        if not self.pk:
            signals.identifier_added.send(self)
        elif 'value' in self.get_stale_fields():
            signals.identifier_changed.send(self, old_value=dirty_fields['value'])
        super(Identifier, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        signals.identifier_removed.send(self)
        super(Identifier, self).delete(*args, **kwargs)
