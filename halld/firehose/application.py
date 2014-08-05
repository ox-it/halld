# Design based on http://toastdriven.com/blog/2011/jul/31/gevent-long-polling-you/

import calendar
import datetime
import http.client
import urllib.parse
import pickle

from gevent import monkey
import gevent
from gevent import pywsgi
from gevent import queue
import redis

import dateutil.parser
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
import pytz
import ujson

from ..models import Resource
from ..pubsub.redis import (
    RESOURCE_CREATED,
    RESOURCE_CHANGED,
    RESOURCE_DELETED,
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
        'when': resource.modified.isoformat(),
    }
    body.put(ujson.dumps(event).encode('utf-8') + b'\n')

def firehose(body, username, start):
    user = get_user_model().objects.get(username=username)
    client = redis.Redis(**settings.REDIS_PARAMS)
    pubsub = client.pubsub()
    pubsub.subscribe(RESOURCE_CREATED)
    pubsub.subscribe(RESOURCE_CHANGED)
    pubsub.subscribe(RESOURCE_DELETED)
    messages = pubsub.listen()

    for resource in Resource.objects.filter(modified__gt=start):
        if not user.has_perm('halld.view_resource', resource):
            continue
        if resource.created > start and resource.deleted:
            continue
        if resource.created > start:
            event = 'resource-created'
        elif resource.deleted:
            event = 'resource-deleted'
        else:
            event = 'resource-changed'
        push_resource(body, user, event, resource)

    for message in messages:
        if message['type'] != 'message':
            continue
        data = pickle.loads(message['data'])
        resource = data['resource']
        event = CHANNEL_TO_EVENT[message['channel']]
        push_resource(body, user, event, resource)


def application(environ, start_response):
    remote_user = 'kebl2765' #environ.get('REMOTE_USER')
    if not remote_user:
        start_response('401 UNAUTHORIZED', [])
        return iter([])
    user = authenticate(remote_user=remote_user)
    if not user:
        start_response('403 FORBIDDEN', [])
        return iter([])

    qs = urllib.parse.parse_qs(environ.get('QUERY_STRING', ''))
    if 'start' in qs:
        try:
            start = dateutil.parser.parse(qs['start'][0])
        except ValueError:
            start_response('400 BAD REQUEST', [])
            return iter(['start parameter must be a datetime.\n'])
        if not start.tzinfo:
            start = pytz.timezone(settings.TIME_ZONE).localize(start)
    else:
        start = pytz.utc.localize(datetime.datetime.utcnow())

    start_response('200 OK', [])
    body = queue.Queue()
    gevent.spawn(firehose, body, remote_user, start)
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

