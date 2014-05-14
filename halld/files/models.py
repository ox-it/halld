from django.db import models

from ..models import Resource

def upload_to(instance, filename):
    # Using the identifier is safe as they're stored in a SlugField, which
    # uses only [a-zA-Z0-9_].
    resource = instance.resource
    return '/'.join([resource.type_id,
                     resource.identifier[0:2],
                     resource.identifier[2:4],
                     resource.identifier[4:]])

class ResourceFile(models.Model):
    resource = models.ForeignKey(Resource)
    file = models.FileField(upload_to=upload_to)
    content_type = models.CharField(max_length=80)
