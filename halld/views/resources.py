import http.client
import json

from django.core.paginator import Paginator
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django_conneg.decorators import renderer
from django_conneg.http import HttpResponseCreated

from .base import HALLDView
from .. import exceptions
from ..models import Resource
from ..registry import get_resource_type

__all__ = ['ResourceListView', 'ResourceDetailView']

class ResourceListView(HALLDView):
    def dispatch(self, request, resource_type, **kwargs):
        try:
            resource_type = get_resource_type(resource_type)
        except KeyError:
            raise Http404
        self.exclude_extant = request.GET.get('extant', 'on') == 'off'
        self.exclude_defunct = request.GET.get('defunct', 'off') == 'off'
        return super(ResourceListView, self).dispatch(request, resource_type, **kwargs)

    def get(self, request, resource_type):
        resources = Resource.objects.filter(type_id=resource_type.name)
        if self.exclude_extant:
            resources = resources.filter(extant=False)
        if self.exclude_defunct:
            resources = resources.filter(extant=True)
        paginator = Paginator(resources, 100)
        try:
            page_num = int(request.GET.get('page'))
        except:
            page_num = 1
        self.context['resource_type'] = resource_type
        self.context['paginator'] = paginator
        self.context['page'] = page = paginator.page(page_num)
        self.object_cache.resource.add_many(page.object_list)
        return self.render()

    def hal_json_from_context(self, request, context):
        paginator, page = context['paginator'], context['page']
        resource_type = context['resource_type']

        hal = {}
        hal.update(resource_type.get_type_properties())
        hal.update({
            '@id': '',
            '_links': {
                'first': {'href': self.url_param_replace(page=1)},
                'last': {'href': self.url_param_replace(page=paginator.num_pages)},
                'find': {'href': reverse('halld:resource-list', args=[resource_type.name]) + '/{identifier}',
                         'templated': True},
                'findSource': {'href': reverse('halld:resource-list', args=[resource_type.name]) + '/{identifier}/source/{source}',
                               'templated': True},
                'findSourceList': {'href': reverse('halld:resource-list', args=[resource_type.name]) + '/{identifier}/source',
                                   'templated': True},
            },
            '_embedded': {'item': [self.object_cache.resource.get_hal(resource.href) for resource in page.object_list]},
        })
        if self.exclude_extant:
            hal['_links']['includeExtant'] = {'href': self.url_param_replace(extant=None)}
        else:
            hal['_links']['excludeExtant'] = {'href': self.url_param_replace(extant='off')}
        if self.exclude_defunct:
            hal['_links']['includeDefunct'] = {'href': self.url_param_replace(extant='on')}
        else:
            hal['_links']['excludeDefunct'] = {'href': self.url_param_replace(extant=None)}
        if page.number > 1:
            hal['_links']['previous'] = {'href': self.url_param_replace(page=page.number-1)}
        if page.number < paginator.num_pages:
            hal['_links']['next'] = {'href': self.url_param_replace(page=page.number+1)}
        return hal

    @transaction.atomic
    def post(self, request, resource_type):
        resource = Resource.create(request.user, resource_type)
        return HttpResponseCreated(resource.get_absolute_url())

class ResourceDetailView(HALLDView):
    def dispatch(self, request, resource_type, identifier, **kwargs):
        try:
            resource_type = get_resource_type(resource_type)
        except KeyError:
            raise exceptions.NoSuchResourceType(resource_type)
        if not resource_type.is_valid_identifier(identifier):
            raise exceptions.NotValidIdentifier(identifier)
        href = resource_type.base_url + identifier
        return super(ResourceDetailView, self).dispatch(request, resource_type, identifier, href, **kwargs)

    def get(self, request, resource_type, identifier, href):
        resource = self.object_cache.resource.get(href)
        self.context['resource'] = resource
        self.context['resource_type'] = resource_type
        if resource.deleted:
            raise exceptions.DeletedResource()
        return self.render()

    @transaction.atomic
    def post(self, request, resource_type, identifier, href):
        resource = Resource.create(request.user, resource_type, identifier)
        return HttpResponseCreated(resource.get_absolute_url())

    def hal_json_from_context(self, request, context):
        resource = context['resource']
        data = resource.filter_data(request.user, resource.data)
        hal = resource.get_hal(request.user, self.object_cache, data)
        if not hal.get('_links'):
            hal['_links'] = {}
        for source in resource.source_set.all():
            if not request.user.has_perm('halld.view_source', source):
                continue
            hal['_links']['source:{}'.format(source.type_id)] = {
                'href': source.get_absolute_url(),
            }
        hal['_links']['source'] = {
            'href': reverse('halld:source-list', args=[resource.type_id, resource.identifier]),
        }
        return hal
