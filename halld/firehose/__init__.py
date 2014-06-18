"""
In the style of Twitter's firehose API, a firehose.

A separate WSGI application (i.e. outside of the Django stack), to be run in
a WSGI container that's happy with persistent connections.

The firehose also requires one or more workers to process messages before
they are passed to clients.
"""

