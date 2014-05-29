schema = {
    "type": "array",
    "items": {
        "type": "object",
        "oneOf": [{
            "properties": {
                "method": {"enum": ["PUT"]},
                "resourceHref": {"type": "string", "format": "url"},
                "sourceType": {"type": "string"},
                "data": {"type": "object"},
            },
            "requiredProperties": ["method", "resourceHref", "sourceType", "data"],
        }, {
            "properties": {
                "method": {"enum": ["PATCH"]},
                "resourceHref": {"type": "string", "format": "url"},
                "sourceType": {"type": "string"},
                "patch": {"type": "object"},
            },
            "requiredProperties": ["method", "resourceHref", "sourceType", "patch"],
        }, {
            "properties": {
                "method": {"enum": ["DELETE"]},
                "resourceHref": {"type": "string", "format": "url"},
                "sourceType": {"type": "string"},
            },
            "requiredProperties": ["method", "resourceHref", "sourceType"],
        }, {
            "properties": {
                "method": {"enum": ["MOVE"]},
                "resourceHref": {"type": "string", "format": "url"},
                "sourceType": {"type": "string"},
                "targetResourceHref": {"type": "string", "format": "url"}
            },
            "requiredProperties": ["method", "resourceHref", "sourceType", "targetResourceHref"],
        }],
    },
}