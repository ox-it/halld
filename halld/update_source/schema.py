schema = {
    "type": "object",
    "properties": {
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
                            "patch": {"type": "object"},
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