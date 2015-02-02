import json

import jsonschema
from rest_framework.response import Response

from .base import HALLDView
from .mixins import JSONRequestMixin
from .. import exceptions
from ..models import Identifier, Source
from .. import response_data

__all__ = ['ByIdentifierView']

class ByIdentifierView(HALLDView, JSONRequestMixin):
    schema = {
        'properties': {
            'scheme': {
                'type': 'string',
                'description': 'The identifier scheme for all identifiers you wish to return results.',
            },
            'values': {
                'type': 'array',
                'items': {'type': 'string'},
                'uniqueItems': True,
                'description': 'A list of identifier values for the resources you wish to retrieve.',
            },
            'allInScheme': {
                'type': 'boolean',
                'enum': [True],
                'description': 'If true, all resources with an identifier in the specified scheme will be retrieved.',
            },
            'includeData': {
                'type': 'boolean',
                'description': 'If true, the response will return the full descriptions of the matched resources. Default false.',
            },
            'includeSources': {
                'type': 'array',
                'items': {'type': 'string'},
                'uniqueItems': True,
                'description': 'A list of source type names you want returning with the results. If missing or empty, none will be returned.',
            },
        },
        'required': ['scheme'],
        'oneOf': [{
            'required': ['values'],
        }, {
            'required': ['allInScheme'],
        }],
    }
    def post(self, request):
        query = self.get_request_json()
        try:
            jsonschema.validate(query, self.schema)
        except jsonschema.ValidationError as e:
            raise exceptions.SchemaValidationError(e)

        identifiers = Identifier.objects.filter(scheme=query['scheme'])
        if 'values' in query:
            identifiers = identifiers.filter(value__in=query['values'])
        identifiers = identifiers.select_related('resource')
        resources = set(identifier.resource for identifier in identifiers)

        seen_values = set()
        results = {}
        by_resource = {}

        for identifier in identifiers:
            resource = identifier.resource
            result = {'resource': resource}
            by_resource[resource.pk] = result
            if query.get('includeSources'):
                result['sources'] = {n: None for n in query['includeSources']}
            results[identifier.value] = result
            seen_values.add(identifier.value)

        if query.get('includeSources'):
            for source in Source.objects.filter(resource__in=resources,
                                                type_id__in=query['includeSources']):
                if request.user.has_perm('halld.view_source', source):
                    by_resource[source.resource_id]['sources'][source.type_id] = source

        if 'values' in query:
            for value in set(query['values']) - seen_values:
                results[value] = None

        return Response(response_data.ByIdentifier(results=results,
                                                   object_cache=request.object_cache,
                                                   user=request.user,
                                                   include_data=bool(query.get('includeData'))))
