schema = {
    "type": "object",
    "properties": {
        "performAt": {"type": "string", "format": "date-time"},
        "description": {"type": "string"},
        "updates": {
            "type": "array",
            "items": {
                "type": "object",
                "allOf": [{ # method
                    "properties": {
                        "method": {"enum": ["PUT", "DELETE", "PATCH", "MOVE"]},
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