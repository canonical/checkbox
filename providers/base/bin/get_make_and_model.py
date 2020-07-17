#!/usr/bin/env python3

import shlex
from subprocess import check_output


def print_header(value):
    print("{}:".format(value))


def print_data(key, value):
    print("  {}: {}".format(key, value))


def run_cmd(option):
    cmd = "lshw -C " + option
    out = check_output(shlex.split(cmd), universal_newlines=True)
    return out.split('\n')


def main():
    keys = {'Manufacturer': 'vendor',
            'Model': 'product',
            'Version': 'version'}
    lshw_classes = {'system': 'System',
                    'bus': 'Mainboard'}

    for lshw_class in lshw_classes:
        output = run_cmd(lshw_class)
        data = {}
        for key in keys:
            for line in output:
                if keys[key] in line:
                    data[key] = line.split(':')[1].strip()
                    break
                else:
                    data[key] = "NOT FOUND"

        print_header(lshw_classes[lshw_class])
        for key in data:
            print_data(key, data[key])


if __name__ == "__main__":
    raise SystemExit(main())
