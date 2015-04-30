from ..sources import FileMetadataSourceTypeDefinition
from ....inference import FirstOf

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
                if exif:
                    metadata['exif'] = {PIL.ExifTags.TAGS[k]: (v.decode('utf-8') if isinstance(v, bytes) else v)
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
        elif etree is not None and isinstance(document, etree._ElementTree):
            return self.get_metadata(document.getroot())
        return metadata or None

    def get_inferences(self):
        prefix = '/@source/{}/'.format(self.name)
        return [
            FirstOf('/imageWidth', prefix + 'width'),
            FirstOf('/imageHeight', prefix + 'height'),
            FirstOf('/imageExif', prefix + 'exif'),
            FirstOf('/imageTitle', prefix + 'exif/ImageDescription'),
            FirstOf('/imageTitle', prefix + 'title'),
            FirstOf('/label', prefix + 'title'),
            FirstOf('/copyright', '/imageExif/Copyright'),
            self.infer_coordinates,
        ]

    def infer_coordinates(self, data, **kwargs):
        gps_info = data.resolve('/imageExif/GPSInfo', {})
        gps_info = {PIL.ExifTags.GPSTAGS[k]: (v.decode('utf-8') if isinstance(v, bytes) else v)
                    for k, v in gps_info.items()
                    if k in PIL.ExifTags.GPSTAGS}
        if not all(k in gps_info for k in ('GPSLatitude', 'GPSLatitudeRef',
                                           'GPSLongitude', 'GPSLongitudeRef')):
            return
        data.set('/@point', {'lat': self.parse_exif_gps_coord(gps_info['GPSLatitude'],
                                                              gps_info['GPSLatitudeRef']),
                             'lon': self.parse_exif_gps_coord(gps_info['GPSLongitude'],
                                                              gps_info['GPSLongitudeRef'])})

    def parse_exif_gps_coord(self, value, ref):
        d, m, s = value
        # truediv, because we're >= Py3
        d, m, s = d[0] / d[1], m[0] / m[1], s[0] / s[1]
        return (d + m / 60 + s / 3600) * (1 if ref in ('N', 'W') else -1)
