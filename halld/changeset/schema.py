schema = {
    "type": "object",
    "properties": {
        "performAt": {"type": "string", "format": "date-time"},
        "description": {"type": "string"},
        "errorHandling": {
            "enum": ["fail-first", "try-all", "ignore"],
            "description": "Strategy for handling update errors. 'fail-first'"
              + " stops trying at the first error. 'try-all' will attempt all'"
              + " updates, but will still not apply if any fail. 'ignore'"
              + " will apply all that it can.",
        },
        "updates": {
            "type": "array",
            "items": {
                "type": "object",
                "allOf": [{ # method
                    "properties": {
                        "method": {"enum": ["PUT", "DELETE", "PATCH", "MOVE"]},
                        "id": {
                            "type": "number",
                            "description": "This will be returned alongside errors. Use it to work out which errors correspond to which updates."
                        },
                    },
                    "required": ["method"],
                }, { # locating a source
                    "oneOf": [{
                        "properties": {
                            "resourceHref": {"type": "string", "format": "url"},
                            "sourceType": {"type": "string"},
                        },
                        "required": ["resourceHref", "sourceType"],
                    }, {
                        "properties": {
                            "href": {"type": "string", "format": "uri"},
                        },
                        "required": ["href"],
                    }],
                }, { # each of the methods
                   "oneOf": [{
                        "properties": {
                            "method": {"enum": ["PUT"]},
                            "data": {"type": ["object", "null"]},
                        },
                        "required": ["data"],
                    }, {
                        "properties": {
                            "method": {"enum": ["PATCH"]},
                            "createEmptyIfMissing": {"type": "boolean"},
                            "patch": {"type": "array"},
                        },
                        "required": ["patch"],
                    }, {
                        "properties": {
                            "method": {"enum": ["DELETE"]},
                        },
                    }, {
                        "properties": {
                            "method": {"enum": ["MOVE"]},
                            "targetResourceHref": {"type": "string", "format": "url"}
                        },
                        "required": ["targetResourceHref"],
                    }],
                }],
            },
        },
    },
}