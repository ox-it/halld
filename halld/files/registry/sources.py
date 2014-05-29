import abc

from ...inference import FirstOf
from ...registry import SourceTypeDefinition

class FileMetadataSourceTypeDefinition(SourceTypeDefinition):
    name = 'file-metadata'

    @abc.abstractmethod
    def get_metadata(self, fp):
        return {}

    def patch_acceptable(self, user, source, patch):
        return False
