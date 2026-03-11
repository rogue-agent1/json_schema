#!/usr/bin/env python3
"""JSON Schema validator (draft-07 subset).

Validates JSON data against JSON Schema with support for:
- type, enum, const
- string: minLength, maxLength, pattern
- number: minimum, maximum, multipleOf
- array: items, minItems, maxItems, uniqueItems
- object: properties, required, additionalProperties
- combinators: allOf, anyOf, oneOf, not
- $ref (local only)

Usage:
    python json_schema.py schema.json data.json
    python json_schema.py --test
"""

import json
import re
import sys


class ValidationError:
    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message

    def __repr__(self):
        return f"{self.path}: {self.message}"


def validate(instance, schema, root_schema=None, path="$") -> list:
    """Validate instance against schema. Returns list of errors."""
    if root_schema is None:
        root_schema = schema
    errors = []

    if isinstance(schema, bool):
        if not schema:
            errors.append(ValidationError(path, "Schema is false — always fails"))
        return errors

    # $ref
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref.startswith("#/"):
            parts = ref[2:].split("/")
            resolved = root_schema
            for p in parts:
                resolved = resolved[p]
            return validate(instance, resolved, root_schema, path)

    # type
    if "type" in schema:
        expected = schema["type"]
        if isinstance(expected, str):
            expected = [expected]
        type_map = {
            "string": str, "number": (int, float), "integer": int,
            "boolean": bool, "array": list, "object": dict, "null": type(None)
        }
        matched = False
        for t in expected:
            if t in type_map:
                if isinstance(instance, type_map[t]):
                    if t == "integer" and isinstance(instance, bool):
                        continue
                    matched = True
            if t == "number" and isinstance(instance, (int, float)) and not isinstance(instance, bool):
                matched = True
        if not matched:
            errors.append(ValidationError(path, f"Expected type {schema['type']}, got {type(instance).__name__}"))
            return errors

    # enum
    if "enum" in schema:
        if instance not in schema["enum"]:
            errors.append(ValidationError(path, f"Value not in enum: {schema['enum']}"))

    # const
    if "const" in schema:
        if instance != schema["const"]:
            errors.append(ValidationError(path, f"Expected const {schema['const']}"))

    # String validations
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(ValidationError(path, f"String too short (min {schema['minLength']})"))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(ValidationError(path, f"String too long (max {schema['maxLength']})"))
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(ValidationError(path, f"String doesn't match pattern '{schema['pattern']}'"))

    # Number validations
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(ValidationError(path, f"Value {instance} < minimum {schema['minimum']}"))
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(ValidationError(path, f"Value {instance} > maximum {schema['maximum']}"))
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            errors.append(ValidationError(path, f"Value {instance} <= exclusiveMinimum"))
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            errors.append(ValidationError(path, f"Value {instance} >= exclusiveMaximum"))
        if "multipleOf" in schema and instance % schema["multipleOf"] != 0:
            errors.append(ValidationError(path, f"Value not multiple of {schema['multipleOf']}"))

    # Array validations
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(ValidationError(path, f"Too few items (min {schema['minItems']})"))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(ValidationError(path, f"Too many items (max {schema['maxItems']})"))
        if schema.get("uniqueItems") and len(instance) != len(set(json.dumps(x, sort_keys=True) for x in instance)):
            errors.append(ValidationError(path, "Items not unique"))
        if "items" in schema:
            item_schema = schema["items"]
            for i, item in enumerate(instance):
                errors.extend(validate(item, item_schema, root_schema, f"{path}[{i}]"))

    # Object validations
    if isinstance(instance, dict):
        if "required" in schema:
            for req in schema["required"]:
                if req not in instance:
                    errors.append(ValidationError(path, f"Missing required property '{req}'"))
        if "properties" in schema:
            for key, prop_schema in schema["properties"].items():
                if key in instance:
                    errors.extend(validate(instance[key], prop_schema, root_schema, f"{path}.{key}"))
        if "additionalProperties" in schema:
            ap = schema["additionalProperties"]
            known = set(schema.get("properties", {}).keys())
            for key in instance:
                if key not in known:
                    if ap is False:
                        errors.append(ValidationError(path, f"Additional property '{key}' not allowed"))
                    elif isinstance(ap, dict):
                        errors.extend(validate(instance[key], ap, root_schema, f"{path}.{key}"))

    # Combinators
    if "allOf" in schema:
        for i, sub in enumerate(schema["allOf"]):
            errors.extend(validate(instance, sub, root_schema, path))
    if "anyOf" in schema:
        if not any(len(validate(instance, sub, root_schema, path)) == 0 for sub in schema["anyOf"]):
            errors.append(ValidationError(path, "Doesn't match any of anyOf"))
    if "oneOf" in schema:
        matches = sum(1 for sub in schema["oneOf"] if len(validate(instance, sub, root_schema, path)) == 0)
        if matches != 1:
            errors.append(ValidationError(path, f"Expected exactly 1 oneOf match, got {matches}"))
    if "not" in schema:
        if len(validate(instance, schema["not"], root_schema, path)) == 0:
            errors.append(ValidationError(path, "Should NOT match 'not' schema"))

    return errors


def test():
    print("=== JSON Schema Validator Tests ===\n")

    # Basic type validation
    schema = {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer", "minimum": 0}}, "required": ["name"]}
    assert len(validate({"name": "Alice", "age": 30}, schema)) == 0
    assert len(validate({"age": 30}, schema)) > 0  # missing name
    assert len(validate({"name": "Bob", "age": -1}, schema)) > 0  # negative age
    print("✓ Basic type + required + minimum")

    # String constraints
    s = {"type": "string", "minLength": 2, "maxLength": 5, "pattern": "^[a-z]+$"}
    assert len(validate("abc", s)) == 0
    assert len(validate("a", s)) > 0  # too short
    assert len(validate("ABC", s)) > 0  # pattern fail
    print("✓ String constraints")

    # Array
    a = {"type": "array", "items": {"type": "integer"}, "minItems": 1, "uniqueItems": True}
    assert len(validate([1, 2, 3], a)) == 0
    assert len(validate([], a)) > 0  # too few
    assert len(validate([1, 1], a)) > 0  # not unique
    assert len(validate([1, "x"], a)) > 0  # wrong item type
    print("✓ Array constraints")

    # Enum
    assert len(validate("red", {"enum": ["red", "green", "blue"]})) == 0
    assert len(validate("yellow", {"enum": ["red", "green", "blue"]})) > 0
    print("✓ Enum")

    # anyOf
    schema = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
    assert len(validate("hi", schema)) == 0
    assert len(validate(42, schema)) == 0
    assert len(validate([], schema)) > 0
    print("✓ anyOf")

    # not
    assert len(validate("hi", {"not": {"type": "integer"}})) == 0
    assert len(validate(42, {"not": {"type": "integer"}})) > 0
    print("✓ not")

    # $ref
    root = {
        "definitions": {"positiveInt": {"type": "integer", "minimum": 1}},
        "type": "object",
        "properties": {"count": {"$ref": "#/definitions/positiveInt"}}
    }
    assert len(validate({"count": 5}, root)) == 0
    assert len(validate({"count": 0}, root)) > 0
    print("✓ $ref")

    # additionalProperties
    strict = {"type": "object", "properties": {"x": {"type": "integer"}}, "additionalProperties": False}
    assert len(validate({"x": 1}, strict)) == 0
    assert len(validate({"x": 1, "y": 2}, strict)) > 0
    print("✓ additionalProperties")

    # Error paths
    errs = validate({"name": 123}, {"type": "object", "properties": {"name": {"type": "string"}}})
    assert errs[0].path == "$.name"
    print(f"✓ Error paths: {errs[0]}")

    print("\nAll tests passed! ✓")


def main():
    args = sys.argv[1:]
    if not args or args[0] == "--test":
        test()
    elif len(args) == 2:
        with open(args[0]) as f:
            schema = json.load(f)
        with open(args[1]) as f:
            data = json.load(f)
        errors = validate(data, schema)
        if errors:
            print(f"INVALID — {len(errors)} error(s):")
            for e in errors:
                print(f"  {e}")
            sys.exit(1)
        else:
            print("VALID ✓")
    else:
        print("Usage: json_schema.py schema.json data.json")


if __name__ == "__main__":
    main()
