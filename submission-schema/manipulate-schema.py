#!/usr/bin/env python3
#
# A tool to collapse or rename a type definition in a JSON schema.

import json
import argparse
from typing import Dict, Any, List, Union


def modify_definition(
    schema: Dict[str, Any], definition_key: str, replacement: str, new_name: str
) -> Dict[str, Any]:
    if new_name and definition_key in schema["definitions"]:
        schema["definitions"][new_name] = schema["definitions"][definition_key]
        del schema["definitions"][definition_key]
        replacement = {"$ref": f"#/definitions/{new_name}"}

    if not new_name and definition_key in schema["definitions"]:
        del schema["definitions"][definition_key]

    def replace_refs(
        obj: Union[Dict[str, Any], List[Any]]
    ) -> Union[Dict[str, Any], List[Any]]:
        if isinstance(obj, dict):
            if obj.get("$ref") == f"#/definitions/{definition_key}":
                return replacement
            else:
                return {k: replace_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_refs(elem) for elem in obj]
        else:
            return obj

    return replace_refs(schema)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collapse or rename a type definition in a JSON schema."
    )
    parser.add_argument("schema", type=str, help="Path to the JSON schema file.")
    parser.add_argument(
        "definition",
        type=str,
        help="The key of the definition to remove or rename.",
    )
    parser.add_argument(
        "replacement",
        type=str,
        nargs="?",
        default=None,
        help='The replacement for the definition (e.g., "string"). If renaming, this is ignored.',
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output file path. If not provided, prints to stdout.",
    )
    parser.add_argument(
        "-n",
        "--new-name",
        type=str,
        default=None,
        help="New name for the definition if renaming.",
    )

    args = parser.parse_args()
    if args.new_name and args.replacement:
        parser.error(
            "Replacement (-r/--replacement) is not allowed when renaming a definition."
        )

    with open(args.schema, "r") as file:
        schema = json.load(file)

    modified_schema = modify_definition(
        schema, args.definition, args.replacement, args.new_name
    )

    if args.output:
        with open(args.output, "w") as file:
            json.dump(modified_schema, file, indent=4)
    else:
        print(json.dumps(modified_schema, indent=4))


if __name__ == "__main__":
    main()
