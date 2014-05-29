import PIL

from ..registry import FileMetadataSourceTypeDefinition

class ImageMetadataSourceTypeDefinition(FileMetadataSourceTypeDefinition):
    name = 'file-metadata:image'

    def get_metadata(self, fp):
        metadata = {}
        image = PIL.Image.open(fp)
        metadata['width'], metadata['height'] = image.size
        return metadata
