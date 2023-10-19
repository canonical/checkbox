#!/usr/bin/env python3

import argparse
import json
import os

from genson import SchemaBuilder


def main():
    parser = argparse.ArgumentParser(
        description="Builds a JSON schema from a directory of JSON files."
    )
    parser.add_argument(
        "directory", help="The directory containing the JSON files to process."
    )
    parser.add_argument(
        "--output",
        "-o",
        help="The output file to write the schema to. Defaults to schema.json.",
        default="schema.json",
    )
    args = parser.parse_args()

    builder = SchemaBuilder()

    for filename in os.listdir(args.directory):
        print(f"Processing file: {filename}")
        if filename.endswith(".json"):
            try:
                with open(os.path.join(args.directory, filename), "r") as f:
                    content = json.load(f)
                    builder.add_object(content)
            except json.JSONDecodeError as e:
                print(f"Error loading JSON from {filename}: {e}")
            except Exception as e:
                print(f"Error processing file {filename}: {e}")

    with open(args.output, "w") as f:
        f.write(builder.to_json(indent=4))


if __name__ == "__main__":
    main()
