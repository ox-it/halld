import abc

from halld.definitions import ResourceTypeDefinition
from halld.files.models import ResourceFile

class FileResourceTypeDefinition(ResourceTypeDefinition):
    name = 'file'

    allowable_media_types = None
    maximum_file_size = 10 * 1024 * 1024 # 10MiB

    @abc.abstractmethod
    def parse_file(self, f, content_type):
        return None

    def get_inferences(self):
        return super().get_inferences() + [
            self.add_sha256,
        ]

    def add_sha256(self, resource, data, **kwargs):
        try:
            data.set('/sha256', resource.file.get().sha256)
        except ResourceFile.DoesNotExist:
            pass
