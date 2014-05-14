from ...registry import ResourceTypeDefinition

class FileResourceTypeDefinition(ResourceTypeDefinition):
    allowable_media_types = None
    maximum_file_size = 10 * 1024 * 1024 # 10MiB
