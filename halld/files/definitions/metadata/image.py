from ..sources import FileMetadataSourceTypeDefinition

try:
    import PIL.Image
except ImportError:
    __all__ = []
else:
    __all__ = ['ImageMetadataSourceTypeDefinition']

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
