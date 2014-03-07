from django.db import connection
from django.contrib.gis.db.backends.base import BaseSpatialOperations

is_spatial_backend = isinstance(connection.ops, BaseSpatialOperations)
