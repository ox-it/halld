import functools

from django.conf import settings
from django.dispatch import receiver
import redis
import pickle

from .. import signals

REDIS_PARAMS = getattr(settings, 'REDIS_PARAMS', None)

SOURCE_CREATED = 'halld:pubsub:source:created'
SOURCE_CHANGED = 'halld:pubsub:source:changed'
SOURCE_DELETED = 'halld:pubsub:source:deleted'
SOURCE_MOVED = 'halld:pubsub:source:moved'

RESOURCE_CREATED = b'halld:pubsub:resource:created'
RESOURCE_CHANGED = b'halld:pubsub:resource:changed'
RESOURCE_DELETED = b'halld:pubsub:resource:deleted'

IDENTIFIER_ADDED = 'halld:pubsub:identifier:added'
IDENTIFIER_CHANGED = 'halld:pubsub:identifier:changed'
IDENTIFIER_REMOVED = 'halld:pubsub:identifier:removed'

def publisher(signal, channel):
    def f(func):
        @receiver(signal)
        @functools.wraps(func)
        def g(sender, *args, **kwargs):
            message = func(sender, *args, **kwargs)
            client = redis.Redis(connection_pool=redis_pool)
            client.publish(channel, pickle.dumps(message))
        return g
    return f

if REDIS_PARAMS is not None:
    redis_pool = redis.ConnectionPool(**REDIS_PARAMS)

    @publisher(signals.source_created, SOURCE_CREATED)
    def source_created(sender, **kwargs):
        return {'type': sender.resource.type_id,
                'identifier': sender.resource.identifier,
                'sourceType': sender.type_id,
                'source': sender,
                'href': sender.href,
                'version': sender.version,
                'data': sender.data}

    @publisher(signals.source_changed, SOURCE_CHANGED)
    def source_changed(sender, **kwargs):
        return {'type': sender.resource.type_id,
                'identifier': sender.resource.identifier,
                'sourceType': sender.type_id,
                'source': sender,
                'href': sender.href,
                'version': sender.version,
                'data': sender.data,
                'old_data': kwargs['old_data']}

    @publisher(signals.source_deleted, SOURCE_DELETED)
    def source_deleted(sender, **kwargs):
        return {'type': sender.resource.type_id,
                'identifier': sender.resource.identifier,
                'sourceType': sender.type_id,
                'source': sender,
                'href': sender.href,
                'version': sender.version,
                'old_data': kwargs['old_data']}

    @publisher(signals.resource_created, RESOURCE_CREATED)
    def resource_created(sender, **kwargs):
        return {'type': sender.type_id,
                'identifier': sender.identifier,
                'href': sender.href,
                'version': sender.version,
                'resource': sender}

    @publisher(signals.resource_changed, RESOURCE_CHANGED)
    def resource_changed(sender, **kwargs):
        return {'type': sender.type_id,
                'identifier': sender.identifier,
                'href': sender.href,
                'version': sender.version,
                'old_data': kwargs['old_data'],
                'resource': sender}

    @publisher(signals.resource_deleted, RESOURCE_DELETED)
    def resource_deleted(sender, **kwargs):
        return {'type': sender.type_id,
                'identifier': sender.identifier,
                'href': sender.href,
                'version': sender.version,
                'old_data': kwargs['old_data'],
                'resource': sender}

    @publisher(signals.identifier_added, IDENTIFIER_ADDED)
    def identifier_added(self, sender, **kwargs):
        return {'type': sender.resource.type,
                'identifier': sender.resource.identifier,
                'scheme': sender.scheme,
                'value': sender.value}

    @publisher(signals.identifier_changed, IDENTIFIER_CHANGED)
    def identifier_changed(self, sender, **kwargs):
        return {'type': sender.resource.type,
                'identifier': sender.resource.identifier,
                'scheme': sender.scheme,
                'value': sender.value,
                'old_value': kwargs['old_value']}

    @publisher(signals.identifier_removed, IDENTIFIER_REMOVED)
    def identifier_removed(self, sender, **kwargs):
        return {'type': sender.resource.type,
                'identifier': sender.resource.identifier,
                'scheme': sender.scheme,
                'old_value': sender.value}
