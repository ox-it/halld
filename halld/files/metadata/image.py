import PIL.Image

from ..registry import FileMetadataSourceTypeDefinition

class ImageMetadataSourceTypeDefinition(FileMetadataSourceTypeDefinition):
    name = 'file-metadata:image'

    def get_metadata(self, fp):
        metadata = {}
        try:
            image = PIL.Image.open(fp)
        except OSError: # cannot identify image file
            raise NotImplementedError
        metadata['width'], metadata['height'] = image.size
        return metadata
