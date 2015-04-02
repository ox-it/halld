from halld.files.exceptions import UnparsableFile

try:
    import PIL.Image
except ImportError:
    pass
else:
    class PILFileParserMixin(object):
        pil_content_types = {'image/png', 'image/jpeg', 'image/bmp', 'image/x-bmp',
                             'application/eps', 'application/x-eps', 'image/eps',
                             'image/x-eps', 'image/gif', 'image/jp2', 'image/jpx',
                             'image/jpm', 'image/tiff', 'image/tiff-fx', 'image/x-icon'}

        def parse_file(self, f, content_type):
            if content_type in self.pil_content_types:
                try:
                    return PIL.Image.open(f)
                except OSError as e:
                    raise UnparsableFile from e
            else:
                return super().parse_file(f, content_type)

try:
    from lxml import etree
except ImportError:
    pass
else:
    class XMLFileParserMixin(object):
        def parse_file(self, f, content_type):
            if content_type in {'text/xml', 'application/xml'} or \
               content_type.endswith('+xml'):
                try:
                    return etree.parse(f, resolve_entities=False)
                except etree.XMLSyntaxError as e:
                    raise UnparsableFile from e
            else:
                return super().parse_file(f, content_type)