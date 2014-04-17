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
            },
            'values': {
                'type': 'array',
                'items': {'type': 'string'},
                'uniqueItems': True,
            },
            'includeData': {
                'type': 'boolean',
            },
            'includeSources': {
                'type': 'array',
                'items': {'type': 'string'},
                'uniqueItems': True,
            },
        },
        'required': ['scheme', 'values'],
    }
    def post(self, request):
        query = self.get_request_json()
        try:
            jsonschema.validate(query, self.schema)
        except jsonschema.ValidationError as e:
            raise exceptions.SchemaValidationError(e)
        identifiers = Identifier.objects.filter(scheme=query['scheme'],
                                                value__in=query['values']).select_related('resource')
        if query.get('includeSources'):
            identifiers = identifiers.select_related('resource__source_set')
        seen_values = set()
        results = {}
        for identifier in identifiers:
            resource = identifier.resource
            result = {'type': resource.type_id, 'identifier': resource.identifier}
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
        for value in set(query['values']) - seen_values:
            results[value] = None
        return HttpResponse(json.dumps(results, indent=2), content_type='application/hal+json')