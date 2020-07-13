#!/usr/bin/env python3
import sys
from checkbox_support.parsers.modinfo import ModinfoParser
from subprocess import Popen, PIPE, check_output, CalledProcessError


def main():
    process = Popen('lsmod', stdout=PIPE, stderr=PIPE, universal_newlines=True)
    data = process.stdout.readlines()
    # Delete the first item because it's headers from lsmod output
    data.pop(0)
    module_list = [module.split()[0].strip() for module in data]

    cmd = '/sbin/modinfo'
    for module in sorted(module_list):
        version = ''
        stream = b''
        try:
            stream = check_output([cmd, module],
                                  stderr=PIPE,
                                  universal_newlines=False)
        except CalledProcessError as e:
            if e.returncode != 1:
                raise e
            else:
                version = 'Unavailable'

        stream = stream.decode('utf-8')

        parser = ModinfoParser(stream)

        if not version:
            version = parser.get_field('version')
            if not version:
                version = parser.get_field('vermagic').split()[0]
        print('%s: %s' % (module, version))
    return 0

if __name__ == '__main__':
    sys.exit(main())
