#!/usr/bin/env python3

import sys
import shlex
from subprocess import check_output, CalledProcessError


def main():
    # First, we need to get output
    cmd = "ipmitool mc info"
    try:
        result = check_output(shlex.split(cmd), universal_newlines=True)
    except FileNotFoundError:
        print(
            "ipmitool was not found! Please install it and try again.",
            file=sys.stderr,
        )
        return 1
    except CalledProcessError as e:
        print("Problem running %s.  Error was %s" % (cmd, e), file=sys.stderr)
        return 1
    result = result.split("\n")

    # We need some bits that are formatted oddly so we need to do some parsing
    data = {}
    for line in result:
        if ":" in line:
            key = line.split(":")[0].strip()
            value = line.split(":")[1].strip()
            data[key] = value
            last = (key, [value])
        else:
            # since the last line we matched had a ':', it's key is likely the
            # key for the next few lines that don't have a ':'
            # This should keep adding items to our last key's list until we hit
            # another line with a :, and we start the cycle over again.
            last[1].append(line.strip())
            data[last[0]] = last[1]

    # Now print out what we care about:
    we_care_about = [
        "Manufacturer Name",
        "Manufacturer ID",
        "Product Name",
        "Product ID",
        "Firmware Revision",
        "IPMI Version",
        "Additional Device Support",
    ]

    for field in we_care_about:
        if type(data[field]) is list:
            # Sometimes the first item in the list is ''.  This will remove it
            data[field].remove("")
            print(field.ljust(30), ":", data[field].pop(0))
            for item in data[field]:
                print(" ".ljust(32), item)
        else:
            print(field.ljust(30), ":", data[field])

    return 0


if __name__ == "__main__":
    sys.exit(main())
