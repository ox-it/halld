from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import View
from django_conneg.http import HttpResponseCreated

from ..models import Resource
import halld.exceptions
from ..registry.resources import get_resource_type

from .registry import FileResourceTypeDefinition
from . import exceptions
from .forms import UploadFileForm
from .models import ResourceFile
from ..views.resources import ResourceListView

class FileView(View):
    def process_file(self, request, resource):
        if request.META['CONTENT_TYPE'] == 'multipart/form-data':
            form = UploadFileForm(request.POST, request.FILES)

class FileCreationView(ResourceListView, FileView):
    @method_decorator(login_required)
    @transaction.atomic
    def post(self, request, resource_type):
        if not isinstance(resource_type, FileResourceTypeDefinition):
            return super(FileCreationView, self).post(request, resource_type)

        if not resource_type.user_can_create(request.user):
            d
            raise PermissionDenied
        identifier = resource_type.generate_identifier()
        resource = Resource.objects.create(type_id=resource_type.name,
                                           identifier=identifier,
                                           creator=request.user)
        self.process_file(request, resource)
        return HttpResponseCreated(resource.get_absolute_url())

class FileDetailView(FileView):
    def dispatch(self, request, resource_type, identifier, **kwargs):
        try:
            resource_type = get_resource_type(resource_type)
        except KeyError:
            raise halld.exceptions.NoSuchResourceType(resource_type)
        if not isinstance(resource_type, FileResourceTypeDefinition):
            raise exceptions.NotAFileResourceType(resource_type)
        return super(FileView, self).dispatch(request, resource_type, identifier, **kwargs)

    def get(self, request, resource_type, identifier):
        resource_file = get_object_or_404(Resource, type_id=resource_type.name, identifier=identifier)
        
    
    @method_decorator(login_required)
    def post(self, request, resource_type, identifier):
        pass

    @method_decorator(login_required)
    def put(self, request, resource_type, identifier):
        pass

    @method_decorator(login_required)
    def delete(self, request, resource_type, identifier):
        pass