import json

from django.http import HttpResponse
import jsonschema

from .mixins import JSONRequestMixin
from .. import exceptions
from ..models import Identifier

__all__ = ['ByIdentifierView']

class ByIdentifierView(JSONRequestMixin):
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

        if query.get('includeSources'):
            identifiers = identifiers.select_related('resource__source_set')
        seen_values = set()
        results = {}
        for identifier in identifiers:
            resource = identifier.resource
            result = {'type': resource.type_id, 'identifier': resource.identifier, 'resourceHref': resource.pk}
            if query.get('includeData'):
                data = resource.filter_data(request.user, resource.data)
                result['data'] = resource.get_hal(request.user, data)
            if query.get('includeSources'):
                result['sources'] = {n: None for n in query['includeSources']}
                sources = resource.source_set.filter(type_id__in=query['includeSources'])
                for source in sources:
                    result['sources'][source.type_id] = source.get_hal(request.user)
            results[identifier.value] = result
            seen_values.add(identifier.value)
        if 'values' in query:
            for value in set(query['values']) - seen_values:
                results[value] = None
        return HttpResponse(json.dumps(results, indent=2), content_type='application/hal+json')
