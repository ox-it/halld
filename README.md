# halld

[![Build Status](https://travis-ci.org/ox-it/halld.png?branch=master)](https://travis-ci.org/ox-it/halld) [![Coverage Status](https://coveralls.io/repos/ox-it/halld/badge.png?branch=master)](https://coveralls.io/r/ox-it/halld?branch=master)

A HAL-based RESTful wotsit for storing structured information about things from multiple sources.

Still a work in progress.

## Model

The HTTP resources are laid out like this:

    / (site root)
    /<type> (list of things of a particular type)
    /<type>/<identifier> (a description of a thing)
    /<type>/<identifier>/source/<source> (a description of a thing according to a particular source)

The source documents are plain JSON can be edited using standard HTTP verbs (`GET`, `PUT`, `PATCH`, `DELETE`, `MOVE`), and are combined to produce the thing description documents, which are exposed as HAL-JSON (and soon, JSON-LD and other RDF serializations).

The way that source documents are combined is entirely customizable, using a sequence of methods that perform inferences. Examples include "set this property to be the first of these that exists" and "if we don't already have a location set, follow this containment link and pick it up from there".

You can define link types, causing certain properties to be interpreted as links and expressed in HAL-JSON `_links` and `_embedded` properties.

ACLs will exist so that only certain users can edit particular source document types, and each edit can be validated (so that e.g. only some users can edit a particular property).

