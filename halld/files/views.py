import http.client
import os

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.uploadhandler import TemporaryFileUploadHandler
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import View
from django_conneg.http import HttpResponseCreated

from ..models import Resource
import halld.exceptions
from ..registry.resources import get_resource_type, get_source_type

from .registry import FileResourceTypeDefinition, FileMetadataSourceTypeDefinition
from . import conf
from . import exceptions
from .forms import UploadFileForm
from .models import ResourceFile
from ..views.resources import ResourceListView, ResourceDetailView

class FileView(View):
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

    def update_file_metadata(self, request, resource_file):
        raise NotImplementedError
        sources = []
        for source in resource_file.resource.source_set.all():
            source_type = get_source_type(source.type_id)
            if isinstance(source_type, FileMetadataSourceTypeDefinition):
                sources.append(source)
        if not sources:
            return
        with resource_file.file.open() as fp:
            fp.seek(0)
            source.data = source.get_metadata(fp)
            source.author = source.committer = request.user
            source.save()

    def process_file_from_request_body(self, request, resource_file, content_type):
        handlers = request.upload_handlers
        content_length = int(request.META.get('CONTENT_LENGTH', 0))
        if content_length == 0:
            raise halld.exceptions.MissingContentLength

        handler = TemporaryFileUploadHandler()
        handler.new_file("file", "upload", content_type, content_length)
        counter = 0
        for chunk in request:
            handler.receive_data_chunk(chunk, counter)
            counter += len(chunk)
        resource_file.file = handler.file_complete(content_length)
        resource_file.content_type = content_type
        resource_file.save()

class FileCreationView(ResourceListView, FileView):
    @method_decorator(login_required)
    @transaction.atomic
    def post(self, request, resource_type):
        if not isinstance(resource_type, FileResourceTypeDefinition):
            return super(FileCreationView, self).post(request, resource_type)

        if not resource_type.user_can_create(request.user):
            raise PermissionDenied
        identifier = resource_type.generate_identifier()
        resource = Resource.objects.create(type_id=resource_type.name,
                                           identifier=identifier,
                                           creator=request.user)
        resource_file = ResourceFile(resource=resource)
        self.process_file(request, resource_file)
        return HttpResponseCreated(resource.get_absolute_url())

class FileResourceDetailView(ResourceDetailView):
    def hal_json_from_context(self, request, context):
        hal = super(FileResourceDetailView, self).hal_json_from_context(request, context)
        resource_type, resource = context['resource_type'], context['resource']
        if isinstance(resource_type, FileResourceTypeDefinition):
            # Add the link to the file
            hal['_links']['describes'] = {
                'href': reverse('halld-files:file-detail',
                                args=[resource.type_id,
                                      resource.identifier]),
                'type': ResourceFile.objects.get(resource=resource).content_type,
            }
        return hal

class FileDetailView(FileView):
    def dispatch(self, request, resource_type, identifier, **kwargs):
        try:
            resource_type = get_resource_type(resource_type)
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
