import http.client
import json

from django.core.exceptions import PermissionDenied
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
        return super(ResourceListView, self).dispatch(request, resource_type, **kwargs)

    def get(self, request, resource_type):
        paginator = Paginator(Resource.objects.filter(type_id=resource_type.name), 100)
        try:
            page_num = int(request.GET.get('page'))
        except:
            page_num = 1
        page = paginator.page(page_num)
        self.context.update(resource_type.get_type_properties())
        self.context.update({
            '@id': '',
            '_links': {
                'first': {'href': '?page=1'},
                'last': {'href': '?page={0}'.format(paginator.num_pages)},
                'find': {'href': reverse('halld:resource-list', args=[resource_type.name]) + '/{identifier}',
                         'templated': True},
                'findSource': {'href': reverse('halld:resource-list', args=[resource_type.name]) + '/{identifier}/source/{source}',
                               'templated': True},
                'findSourceList': {'href': reverse('halld:resource-list', args=[resource_type.name]) + '/{identifier}/source',
                                   'templated': True},
            },
            '_embedded': {'item' :[resource.get_hal(request.user) for resource in page.object_list]},
        })
        if page_num > 1:
            self.context['_links']['previous'] = {'href': '?page={0}'.format(page_num - 1)}
        if page_num < paginator.num_pages:
            self.context['_links']['next'] = {'href': '?page={0}'.format(page_num + 1)}
        
        return self.render()

    @transaction.atomic
    def post(self, request, resource_type):
        if not resource_type.user_can_create(request.user):
            raise PermissionDenied
        identifier = resource_type.generate_identifier()
        resource = Resource.objects.create(type_id=resource_type.name,
                                           identifier=identifier,
                                           creator=request.user)
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
        resource = get_object_or_404(Resource, href=href)
        self.context['resource'] = resource
        if resource.deleted:
            raise Http404
        elif not resource.extant:
            self.context['status_code'] = http.client.GONE
            
        #if resource.moved_to:
        #    return HttpResponsePermanentRedirect(resource.moved_to.get_absolute_url())
        return self.render()

    @transaction.atomic
    def post(self, request, resource_type, identifier, href):
        if not resource_type.user_can_create(request.user):
            raise PermissionDenied
        try:
            resource = Resource.objects.get(href=href)
        except Resource.DoesNotExist:
            if resource_type.user_can_assign_identifier(request.user, identifier):
                resource = Resource.objects.create(type_id=resource_type.name,
                                                   identifier=identifier,
                                                   creator=request.user)
                return HttpResponseCreated(resource.get_absolute_url())
            else:
                raise exceptions.CannotAssignIdentifier
        else:
            raise exceptions.ResourceAlreadyExists(resource)

    @renderer(format='hal', mimetypes=('application/hal+json',), name='HAL/JSON')
    def render_hal(self, request, context, template_name):
        resource = context['resource']
        data = resource.filter_data(request.user, resource.data)
        hal = resource.get_hal(request.user, data)
        for source in resource.source_set.all():
            if not request.user.has_perm('halld.view_source', source):
                continue
            hal['_links']['source:{}'.format(source.type_id)] = {
                'href': source.get_absolute_url(),
            }
        hal['_links']['source'] = {
            'href': reverse('halld:source-list', args=[resource.type_id, resource.identifier]),
        }
        return HttpResponse(json.dumps(hal, indent=2, sort_keys=True),
                            content_type='application/hal+json')
