#!/usr/bin/python3

import os
import sys
import yaml


def read_yaml(filename="media_source.yaml"):
    plainbox_provider_data = os.path.expandvars("$PLAINBOX_PROVIDER_DATA")
    yaml_path = os.path.join(plainbox_provider_data, filename)
    with open(yaml_path, "r") as file:
        data = yaml.safe_load(file)

    return data["media"]


def main():
    media_sources = read_yaml()
    for media in media_sources:
        print("")
        for key in media:
            print("%s: %s" % (key, media[key]))


if __name__ == "__main__":
    sys.exit(main())
