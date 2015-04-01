from ..sources import FileMetadataSourceTypeDefinition

try:
    from PIL.Image import Image
    import PIL.ExifTags
except ImportError:
    Image = None

try:
    from lxml import etree
except ImportError:
    etree = None

namespaces = {
    'svg': 'http://www.w3.org/2000/svg',
}

class ImageMetadataSourceTypeDefinition(FileMetadataSourceTypeDefinition):
    name = 'file-metadata:image'

    def get_metadata(self, document):
        metadata = {}
        if Image is not None and isinstance(document, Image):
            metadata['width'], metadata['height'] = document.size
            if hasattr(document, '_getexif'):
                exif = document._getexif()
                metadata['exif'] = {PIL.ExifTags.TAGS[k]: v
                                    for k, v in exif.items()
                                    if k in PIL.ExifTags.TAGS}
        elif etree is not None and isinstance(document, etree._Element):
            if document.xpath('self::svg:svg[@width and @height]', namespaces=namespaces):
                w, h = document.attrib['width'], document.attrib['height']
                if w.endswith('px'): w = w[:-2]
                if h.endswith('px'): h = h[:-2]
                try:
                    metadata['width'], metadata['height'] = int(w), int(h)
                except ValueError:
                    pass
                title = document.xpath('svg:title/text()', namespaces=namespaces)
                if title:
                    metadata['title'] = title[0]
        return metadata or None
