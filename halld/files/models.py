import hashlib
import os

from django.conf import settings
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
    resource = models.ForeignKey(Resource, related_name='file')
    file = models.FileField(upload_to=upload_to)
    content_type = models.CharField(max_length=80)
    sha256 = models.CharField(max_length=64)

    def update_sha256(self):
        sha256 = hashlib.sha256()
        blocksize = os.stat(self.file.path).st_blksize
        with open(self.file.path, 'rb') as f:
            while True:
                block = f.read(blocksize)
                if block:
                    sha256.update(block)
                else:
                    break
        self.sha256 = sha256.hexdigest()
