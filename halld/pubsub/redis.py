import functools

from django.conf import settings
import redis
import ujson

from .. import signals

REDIS_PARAMS = getattr(settings, 'REDIS_PARAMS', None)

SOURCEDATA_CREATED = 'halld:pubsub:sourcedata:created'
SOURCEDATA_CHANGED = 'halld:pubsub:sourcedata:changed'
SOURCEDATA_DELETED = 'halld:pubsub:sourcedata:deleted'
SOURCEDATA_MOVED = 'halld:pubsub:sourcedata:moved'

RESOURCE_CREATED = 'halld:pubsub:resource:created'
RESOURCE_CHANGED = 'halld:pubsub:resource:changed'
RESOURCE_DELETED = 'halld:pubsub:resource:deleted'

IDENTIFIER_ADDED = 'halld:pubsub:identifier:added'
IDENTIFIER_CHANGED = 'halld:pubsub:identifier:changed'
IDENTIFIER_REMOVED = 'halld:pubsub:identifier:removed'

def publisher(signal, channel):
    def f(func):
        @signal.connect
        @functools.wraps(func)
        def g(sender, *args, **kwargs):
            message = func(sender, *args, **kwargs)
            client = redis.Redis(connection_pool=redis_pool)
            client.publish(channel, ujson.dumps(message))
        return g
    return f

if REDIS_PARAMS is not None:
    redis_pool = redis.ConnectionPool(**REDIS_PARAMS)

    @publisher(signals.sourcedata_created, SOURCEDATA_CREATED)
    def sourcedata_created(sender, **kwargs):
        return {'type': sender.resource.type,
                'identifier': sender.resource.identifier,
                'source': sender.source_id,
                'version': sender.version,
                'data': sender.data}

    @publisher(signals.sourcedata_changed, SOURCEDATA_CHANGED)
    def sourcedata_changed(sender, **kwargs):
        return {'type': sender.resource.type,
                'identifier': sender.resource.identifier,
                'source': sender.source_id,
                'version': sender.version,
                'data': sender.data,
                'old_data': kwargs['old_data']}

    @publisher(signals.sourcedata_deleted, SOURCEDATA_DELETED)
    def sourcedata_deleted(sender, **kwargs):
        return {'type': sender.resource.type,
                'identifier': sender.resource.identifier,
                'source': sender.source_id,
                'version': sender.version,
                'old_data': sender.data}

    @publisher(signals.resource_created, RESOURCE_CREATED)
    def resource_created(sender, **kwargs):
        return {'type': sender.resource.type,
                'identifier': sender.identifier,
                'version': sender.version,
                'data': sender.data}

    @publisher(signals.resource_changed, RESOURCE_CHANGED)
    def resource_changed(sender, **kwargs):
        return {'type': sender.resource.type,
                'identifier': sender.identifier,
                'version': sender.version,
                'data': sender.data,
                'old_data': kwargs['old_data']}

    @publisher(signals.resource_deleted, RESOURCE_DELETED)
    def resource_deleted(sender, **kwargs):
        return {'type': sender.type,
                'identifier': sender.identifier,
                'version': sender.version,
                'old_data': sender.data}

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
