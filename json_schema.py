#!/usr/bin/env python3
"""JSON Schema Validator — validate JSON data against schemas."""
import re

def validate(data, schema, path="$"):
    errors = []
    stype = schema.get("type")
    if stype:
        type_map = {"string": str, "number": (int,float), "integer": int, 
                     "boolean": bool, "array": list, "object": dict, "null": type(None)}
        expected = type_map.get(stype)
        if expected and not isinstance(data, expected):
            errors.append(f"{path}: expected {stype}, got {type(data).__name__}")
            return errors
    if stype == "object":
        for prop, pschema in schema.get("properties", {}).items():
            if prop in data:
                errors.extend(validate(data[prop], pschema, f"{path}.{prop}"))
            elif prop in schema.get("required", []):
                errors.append(f"{path}.{prop}: required")
        if "additionalProperties" in schema and not schema["additionalProperties"]:
            extra = set(data.keys()) - set(schema.get("properties", {}).keys())
            for k in extra: errors.append(f"{path}.{k}: additional property not allowed")
    if stype == "array":
        if "items" in schema:
            for i, item in enumerate(data):
                errors.extend(validate(item, schema["items"], f"{path}[{i}]"))
        if "minItems" in schema and len(data) < schema["minItems"]:
            errors.append(f"{path}: min {schema['minItems']} items, got {len(data)}")
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            errors.append(f"{path}: max {schema['maxItems']} items, got {len(data)}")
    if stype == "string":
        if "minLength" in schema and len(data) < schema["minLength"]:
            errors.append(f"{path}: minLength {schema['minLength']}")
        if "pattern" in schema and not re.match(schema["pattern"], data):
            errors.append(f"{path}: pattern mismatch")
    if stype in ("number", "integer"):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{path}: minimum {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(f"{path}: maximum {schema['maximum']}")
    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']}")
    return errors

if __name__ == "__main__":
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "age": {"type": "integer", "minimum": 0, "maximum": 150},
            "email": {"type": "string", "pattern": r"^[^@]+@[^@]+\.[^@]+$"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 5}
        },
        "required": ["name", "age"]
    }
    good = {"name": "Alice", "age": 30, "email": "alice@example.com", "tags": ["dev"]}
    bad = {"name": "", "age": -5, "email": "invalid", "tags": [1, 2]}
    print(f"Valid: {validate(good, schema)}")
    print(f"Invalid: {validate(bad, schema)}")
