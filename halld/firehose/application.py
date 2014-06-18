import calendar
import datetime
import http.client
import pickle

from gevent import monkey
import gevent
from gevent import pywsgi
from gevent import queue
import redis

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
import pytz
import ujson

from ..models import Resource, Identifier
from ..pubsub.redis import (
    RESOURCE_CREATED,
    RESOURCE_CHANGED,
    RESOURCE_DELETED,
    IDENTIFIER_ADDED,
    IDENTIFIER_CHANGED,
    IDENTIFIER_REMOVED,
)

CHANNEL_TO_EVENT = {
    RESOURCE_CREATED: 'resource-created',
    RESOURCE_CHANGED: 'resource-changed',
    RESOURCE_DELETED: 'resource-deleted',
}

LAST_SEEN = 'halld:firehose:last-seen'

def push_resource(body, user, event, resource):
    data = None if resource.deleted else resource.filter_data(user)
    event = {
        'event': event,
        'resourceType': resource.type_id,
        'identifier': resource.identifier,
        'data': data,
        'href': resource.href,
    }
    body.put(ujson.dumps(event).encode('utf-8') + b'\n')

def firehose(body, username):
    user = get_user_model().objects.get(username=username)
    client = redis.Redis(**settings.REDIS_PARAMS)
    pubsub = client.pubsub()
    pubsub.subscribe(RESOURCE_CREATED)
    pubsub.subscribe(RESOURCE_CHANGED)
    pubsub.subscribe(RESOURCE_DELETED)
#    pubsub.psubscribe('*')
    messages = pubsub.listen()

    last_seen = client.zscore(LAST_SEEN, user.username) or 0
    last_seen = pytz.utc.localize(datetime.datetime.fromtimestamp(last_seen))
    last_modified = last_seen

    for resource in Resource.objects.filter(modified__gt=last_seen):
        if not user.has_perm('halld.view_resource', resource):
            continue
        if resource.created > last_seen and resource.deleted:
            continue
        if resource.created > last_seen:
            event = 'resource-created'
        elif resource.deleted:
            event = 'resource-deleted'
        else:
            event = 'resource-changed'
        push_resource(body, user, event, resource)
        last_modified = max(last_modified, resource.modified)
       
    client.zadd(LAST_SEEN, username,
                calendar.timegm(last_modified.timetuple()))

    for message in messages:
        import sys
        sys.stderr.write(message['type'])
        sys.stderr.write('\n')
        if message['type'] != 'message':
            continue
        data = pickle.loads(message['data'])
        resource = data['resource']
        event = CHANNEL_TO_EVENT[message['channel']]
        push_resource(body, user, event, resource)


def application(environ, start_response):
    username = environ.get('REMOTE_USER')
    if not username:
        start_response('401 UNAUTHORIZED', [])
        return iter([])
    user = True #authenticate(username=username)
    if not user:
        start_response('403 FORBIDDEN', [])
        return iter([])

    start_response('200 OK', [])
    body = queue.Queue()
    gevent.spawn(firehose, body, username)
    return body

def initialize():
<<<<<<< HEAD
    # Patching thread makes Django's database connection wrapper get upset
    # about turning up in threads it wasn't expecting.
    monkey.patch_all(socket=True, dns=True, time=True, select=True,
                     thread=False, os=True, ssl=True, httplib=False,
                     aggressive=True)
    # For some reason this is missing, but expected, in Py3.3
=======
    monkey.patch_all(socket=True, dns=True, time=True, select=True,thread=False, os=True, ssl=True, httplib=False, aggressive=True)
    # For some reason this is missing, but expected in Py3.3
>>>>>>> A working firehose
    if not hasattr(http.client, '_MAXHEADERS'):
        http.client._MAXHEADERS = 100

if __name__ == '__main__':
    initialize()
    server = pywsgi.WSGIServer(('127.0.0.1', 8002), application)
    server.serve_forever()

