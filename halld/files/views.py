import copy
import http.client
import os

from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from rest_framework.parsers import FileUploadParser

from .. import get_halld_config
from ..models import Resource
import halld.exceptions
from ..changeset import SourceUpdater
from .definitions import FileResourceTypeDefinition, FileMetadataSourceTypeDefinition
from . import conf
from . import exceptions
from .forms import UploadFileForm
from .models import ResourceFile
from ..views.resources import ResourceListView
from ..views.base import HALLDView

class FileView(HALLDView):
    parser_classes = (FileUploadParser,)

    # Needed, otherwise filename will be None, and rest_framework will assume
    # no file has been uploaded.
    def get_parser_context(self, http_request):
        parser_context = copy.deepcopy(super().get_parser_context(http_request))
        parser_context['kwargs']['filename'] = 'uploaded-file'
        return parser_context

    def process_file(self, request, resource_file):
        try:
            content_type = request.META['CONTENT_TYPE'].split(';')[0].strip()
        except KeyError:
            raise halld.exceptions.MissingContentType
        if content_type == 'multipart/form-data':
            form = UploadFileForm(request.POST, request.FILES, instance=resource_file)
            if form.is_valid():
                form.save()
            else:
                raise exceptions.InvalidMultiPartFileCreation(form.errors)
        elif content_type == 'application/x-www-form-urlencoded':
            raise exceptions.NoFileUploaded
        else:
            self.process_file_from_request_body(request, resource_file, content_type)
        self.update_file_metadata(request, resource_file)

    def process_file_from_request_body(self, request, resource_file, content_type):
        try:
            file = request.data['file']
        except KeyError:
            raise exceptions.NoFileUploaded

        resource_file.file = file
        resource_file.content_type = request.content_type
        if not resource_file.content_type:
            raise halld.exceptions.MissingContentType
        resource_file.save()

    def update_file_metadata(self, request, resource_file):
        source_types = resource_file.resource.get_type().source_types
        source_types = (get_halld_config().source_types[source_type] for source_type in source_types)
        source_types = [source_type for source_type in source_types
                        if isinstance(source_type, FileMetadataSourceTypeDefinition)]
        if not source_types:
            return
        updates = []
        resource_file.file.open()
        try:
            for source_type in source_types:
                resource_file.file.seek(0)
                try:
                    data = source_type.get_metadata(resource_file.file)
                except NotImplementedError:
                    data = None
                update = {
                    'method': 'PUT',
                    'resourceHref': resource_file.resource_id,
                    'sourceType': source_type.name,
                    'data': data,
                }
                updates.append(update)
        finally:
            resource_file.file.close()

        committer = get_user_model().objects.get(username=conf.FILE_METADATA_USER)
        source_updater = SourceUpdater(request.build_absolute_uri(),
                                       author=request.user,
                                       committer=committer)
        source_updater.perform_updates({'updates': updates})

class FileCreationView(ResourceListView, FileView):
    @method_decorator(login_required)
    @transaction.atomic
    def post(self, request, resource_type):
        if not isinstance(self.resource_type, FileResourceTypeDefinition):
            return super().post(request, self.resource_type)

        if not self.resource_type.user_can_create(request.user):
            raise halld.exceptions.Forbidden(request.user)
        identifier = self.resource_type.generate_identifier()
        resource = Resource.objects.create(type_id=self.resource_type.name,
                                           identifier=identifier,
                                           creator=request.user)
        resource_file = ResourceFile(resource=resource)
        self.process_file(request, resource_file)
        response = HttpResponse('', status=http.client.CREATED)
        response['Location'] = resource.get_absolute_url()
        return response

class FileDetailView(FileView):
    def dispatch(self, request, resource_type, identifier, **kwargs):
        try:
            resource_type = get_halld_config().resource_types[resource_type]
        except KeyError:
            raise halld.exceptions.NoSuchResourceType(resource_type)
        if not isinstance(resource_type, FileResourceTypeDefinition):
            raise exceptions.NotAFileResourceType(resource_type)
        href = request.build_absolute_uri(reverse('halld:resource-detail',
                                                  args=[resource_type.name, identifier]))
        resource = get_object_or_404(Resource, href=href)
        resource_file = ResourceFile.objects.get(resource=resource)
        return super(FileView, self).dispatch(request, resource_file, **kwargs)

    def get(self, request, resource_file):
        if conf.USE_XSENDFILE:
            response = HttpResponse(content_type=resource_file.content_type)
            response['X-Send-File'] = resource_file.file.path
        else:
            f = open(resource_file.file.path, 'r')
            response = StreamingHttpResponse(f,
                                             content_type=resource_file.content_type)
            response['Content-Length'] = os.fstat(f.fileno()).st_size
        return response
    
    @method_decorator(login_required)
    def post(self, request, resource_file):
        self.process_file(request, resource_file)
        return HttpResponse('', status=http.client.NO_CONTENT)

    @method_decorator(login_required)
    def put(self, request, resource_file):
        self.process_file(request, resource_file)
        return HttpResponse('', status=http.client.NO_CONTENT)
