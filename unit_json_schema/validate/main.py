#!/usr/bin/env python3
"""
Validate multi-document YAML files against a JSON Schema.

This script must be able to:
- Validate given multiple schema files
- Validate yaml natively
- Validate multi document yamls

Replace this with an out of the box tool if found
"""

import json
import argparse
from pathlib import Path

import yaml
from referencing import Registry, Resource
from jsonschema import Draft202012Validator


def load_schemas(schema_dir: Path) -> Registry:
    """Load all .json schemas from a directory into a registry."""
    resources = []
    for schema_path in schema_dir.glob("*.schema.json"):
        with schema_path.open() as f:
            schema = json.load(f)
        uri = schema.get("$id", schema_path.name)
        resource = Resource.from_contents(schema)
        resources.append((uri, resource))
        if uri != schema_path.name:
            resources.append((schema_path.name, resource))
    return Registry().with_resources(resources)


def validate_file(
    validator: Draft202012Validator, yaml_path: Path
) -> list[str]:
    """Validate all YAML documents in a file. Returns list of errors string"""
    errors = []
    with open(yaml_path) as f:
        documents = yaml.safe_load_all(f)
        for doc_index, doc in enumerate(documents, 1):
            if doc is None:
                continue
            for error in validator.iter_errors(doc):
                path = (
                    ".".join(str(p) for p in error.absolute_path) or "(root)"
                )
                errors.append(f"  doc {doc_index}, {path}: {error.message}")
    return errors


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "schema", help="Location for the main schema file", type=Path
    )
    parser.add_argument(
        "yamls", nargs="+", help="YAML files to validate", type=Path
    )
    return parser.parse_args()


def main():
    args = parse_args()
    yaml_paths = args.yamls

    with open(args.schema) as f:
        main_schema = json.load(f)

    registry = load_schemas(args.schema.parent)
    validator = Draft202012Validator(main_schema, registry=registry)

    failed = False
    for yaml_path in yaml_paths:
        errors = validate_file(validator, yaml_path)
        if errors:
            failed = True
            print(f"FAIL {yaml_path}")
            for e in errors:
                print(e)
        else:
            print(f"OK   {yaml_path}")

    if failed:
        raise SystemExit("Some paths failed to validate")


if __name__ == "__main__":
    main()
