import abc

from halld.definitions import SourceTypeDefinition

class FileMetadataSourceTypeDefinition(SourceTypeDefinition):
    @abc.abstractmethod
    def get_metadata(self, document):
        return {}

    def patch_acceptable(self, user, source, patch):
        return False
