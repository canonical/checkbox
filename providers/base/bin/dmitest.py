#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
#
# Test for sane dmidecode output, particularly with respect to
# various manufacturer information fields. Also, verify that the
# system reports a chassis type that suits its class (server or
# desktop/laptop)
#
# By: Rod Smith

"""Script to test dmidecode output for sanity.

:param --dmifile:
    Input filename; optional. If specified, file is used instead of
    dmidecode output.
:param --show_dmi:
    Print the DMI data used. For debugging purposes if errors are encountered.
:param --test_versions:
    Include chassis, system, and base boad version numbers among tests.
:param --test_serials:
    Include system and base board serial numbers among tests.
:param cpu_check:
    Don't perform usual tests, except for CPU test.
:param desktop:
    SUT is a desktop or laptop
:param server:
    SUT is a server
"""

import re
import subprocess
import sys

from argparse import ArgumentParser


def find_in_section(stream, dmi_data, section, label, strings, find_empty):
    """Search for a set of strings on a line in the output.

    :param stream:
        input text stream (dmidecode output)
    :param section:
        section label in which to search (e.g., "Chassis Information")
    :param label:
        label of line on which to search (e.g., "Type:")
    :param strings:
        set of strings for which to search (e.g., ["server", "blade"])
    :param find_empty:
        if True, matches empty label field (as if '""' were passed as
        a strings value)
    :returns found:
        True if one or more of strings was found on "label" line in "section"
        section, or if "label" line is empty AND find_empty is True;
        False otherwise
    """
    start_looking = False
    found = False
    empty = True
    for line in stream:
        if line == section:
            start_looking = True
        if start_looking and re.search(label, line):
            line_items = line.strip().split(':')
            dmi_data[section][line_items[0]] = line_items[1]
            empty = len(line.strip()) == len(label)
            if empty and find_empty:
                found = True
            for s in strings:
                if re.search(s, line, flags=re.IGNORECASE):
                    found = True
                    break
            start_looking = False

    return found


def standard_tests(args, stream, dmi_data):
    """
    Perform the standard set of tests.

    :param args:
        Arguments passed to script
    :param stream:
        Input stream containing dmidecode output
    :returns retval:
        Number of problems found
    """
    retval = 0
    """
    NOTE: System type is encoded in both the "Chassis Information" and "Base
    Board Type" sections. The former is more reliable, so we do a whitelist
    test on it -- the type MUST be specified correctly. The "Base Board Type"
    section is less reliable, so rather than flag large numbers of systems
    for having "Unknown", "Other", or something similar here, we just flag
    it when it's at odds with the type passed on the command line. Also,
    the "Base Board Type" may specify a desktop or tower system on servers
    shipped in those form factors, so we don't flag that combination as an
    error.
    """
    if args.test_type == 'server':
        if not find_in_section(stream, dmi_data, 'Chassis Information',
                               'Type:',
                               ['server', 'rack mount', 'blade', 'other',
                                'expansion chassis', 'multi-system', 'tower'],
                               False):
            dmi_data['Chassis Information']['Type'] += \
                    " *** Incorrect or unknown server chassis type!"
            retval += 1
        if find_in_section(stream, dmi_data, 'Base Board Information', 'Type:',
                           ['portable', 'notebook', 'space-saving',
                            'all in one'], False):
            dmi_data['Base Board Information']['Type'] += \
                    " *** Incorrect server base board type!"
            retval += 1
    else:
        if not find_in_section(stream, dmi_data, 'Chassis Information',
                               'Type:',
                               ['notebook', 'portable', 'laptop', 'desktop',
                                'lunch box', 'space-saving', 'tower',
                                'all in one', 'hand held',
                                'convertible'], False):
            dmi_data['Chassis Information']['Type'] += \
                    " *** Incorrect or unknown desktop chassis type!"
            retval += 1
        if find_in_section(stream, dmi_data, 'Base Board Information', 'Type:',
                           ['rack mount', 'server', 'multi-system',
                            'interconnect board'], False):
            dmi_data['Base Board Information']['Type'] += \
                    " *** Incorrect desktop base board type!"
            retval += 1
    if find_in_section(stream, dmi_data, 'Chassis Information',
                       'Manufacturer:',
                       ['empty', 'chassis manufacture', 'null', 'insyde',
                        r'to be filled by o\.e\.m\.', 'no enclosure',
                        r'\.\.\.\.\.'], True):
        dmi_data['Chassis Information']['Manufacturer'] += \
                " *** Invalid chassis manufacturer!"
        retval += 1
    if find_in_section(stream, dmi_data, 'System Information', 'Manufacturer:',
                       ['system manufacture', 'insyde', 'standard',
                        r'to be filled by o\.e\.m\.', 'no enclosure'], True):
        dmi_data['System Information']['Manufacturer'] += \
                " *** Invalid system manufacturer!"
        retval += 1
    if find_in_section(stream, dmi_data, 'Base Board Information',
                       'Manufacturer:',
                       [r'to be filled by o\.e\.m\.'], True):
        dmi_data['Base Board Information']['Manufacturer'] += \
                " *** Invalid base board manufacturer!"
        retval += 1
    if find_in_section(stream, dmi_data, 'System Information',
                       'Product Name:',
                       ['system product name', r'to be filled by o\.e\.m\.'],
                       False):
        dmi_data['System Information']['Product Name'] += \
                " *** Invalid system product name!"
        retval += 1
    if find_in_section(stream, dmi_data, 'Base Board Information',
                       'Product Name:',
                       ['base board product name',
                        r'to be filled by o\.e\.m\.'], False):
        dmi_data['Base Board Information']['Product Name'] += \
                " *** Invalid base board product name!"
        retval += 1
    return retval


def version_tests(args, stream, dmi_data):
    """
    Perform the version tests.

    :param args:
        Arguments passed to script
    :param stream:
        Input stream containing dmidecode output
    :returns retval:
        Number of problems found
    """
    retval = 0
    if find_in_section(stream, dmi_data, 'Chassis Information', 'Version:',
                       [r'to be filled by o\.e\.m\.', 'empty', r'x\.x'],
                       False):
        dmi_data['Chassis Information']['Version'] += \
                " *** Invalid chassis version!"
        retval += 1
    if find_in_section(stream, dmi_data, 'System Information', 'Version:',
                       [r'to be filled by o\.e\.m\.', r'\(none\)',
                        'null', 'system version', 'not applicable',
                        r'\.\.\.\.\.'], False):
        dmi_data['System Information']['Version'] += \
                " *** Invalid system information version!"
        retval += 1
    if find_in_section(stream, dmi_data, 'Base Board Information', 'Version:',
                       ['base board version', r'x\.x',
                        'empty', r'to be filled by o\.e\.m\.'], False):
        dmi_data['Base Board Information']['Version'] += \
                " *** Invalid base board version!"
        retval += 1
    return retval


def serial_tests(args, stream, dmi_data):
    """
    Perform the serial number tests.

    :param args:
        Arguments passed to script
    :param stream:
        Input stream containing dmidecode output
    :returns retval:
        Number of problems found
    """
    retval = 0
    if find_in_section(stream, dmi_data, 'System Information',
                       'Serial Number:',
                       [r'to be filled by o\.e\.m\.',
                        'system serial number', r'\.\.\.\.\.'],
                       False):
        dmi_data['System Information']['Serial Number'] += \
                " *** Invalid system information serial number!"
        retval += 1
    if find_in_section(stream, dmi_data, 'Base Board Information',
                       'Serial Number:',
                       ['n/a', 'base board serial number',
                        r'to be filled by o\.e\.m\.',
                        'empty', r'\.\.\.'],
                       False):
        dmi_data['Base Board Information']['Serial Number'] += \
                " *** Invalid base board serial number!"
        retval += 1
    return retval


def main():
    """Main function."""
    parser = ArgumentParser()
    parser.add_argument('test_type',
                        help="Test type ('server', 'desktop' or 'cpu-check').",
                        choices=['server', 'desktop', 'cpu-check'])
    parser.add_argument('--dmifile',
                        help="File to use in lieu of dmidecode.")
    parser.add_argument('--show_dmi', action="store_true",
                        help="Print DMI Data used for debugging purposes.")
    parser.add_argument('--test_versions', action="store_true",
                        help="Set to check version information")
    parser.add_argument('--test_serials', action="store_true",
                        help="Set to check serial number information")
    args = parser.parse_args()

    bad_data = False
    dmi_data = {'System Information': {},
                'Base Board Information': {},
                'Chassis Information': {},
                'Processor Information': {}}

    # Command to retrieve DMI information
    COMMAND = "dmidecode"
    if args.dmifile:
        COMMAND = ['cat', args.dmifile]
        print("Reading " + args.dmifile + " as DMI data")
    try:
        dmi_out = subprocess.check_output(COMMAND).splitlines()
    except subprocess.CalledProcessError as err:
        print("Error running {}: {}".format(COMMAND, err))
        return 1

    # Convert the bytes output separately, line by line, because it's possible
    # that someone put non-encodable characters in DMI, which cases a
    # UnicodeDecodeError that is non-helpful.  LP: 1655155
    stream = []
    for line in dmi_out:
        try:
            stream.append(line.decode('utf-8'))
        except UnicodeDecodeError as ude:
            print("DATA ERROR: {}".format(ude))
            print("\tLINE NUMBER {}: {}".format(dmi_out.index(line) + 1, line))
            stream.append("ERROR: BAD DATA FOUND HERE")
            bad_data = True

    if args.show_dmi:
        print("===== DMI Data Used: =====")
        for line in stream:
            print(line)
        print("===== DMI Output Complete =====")

    retval = 0
    if args.test_type == 'server' or args.test_type == 'desktop':
        retval += standard_tests(args, stream, dmi_data)
    if args.test_versions:
        retval += version_tests(args, stream, dmi_data)
    if args.test_serials:
        retval += serial_tests(args, stream, dmi_data)
    if find_in_section(stream, dmi_data, 'Processor Information', 'Version:',
                       ['sample', r'Genuine Intel\(R\) CPU 0000'], False):
        dmi_data['Processor Information']['Version'] += \
            " *** Invalid processor information!"
        retval += 1

    # In review of dmidecode data on 10/23/2014, no conspicuous problems
    # found in BIOS Information section's Vendor, Version, or Release Date
    # fields. Therefore, no tests based on these fields have been written.

    for section in sorted(dmi_data.keys()):
        print('{}:'.format(section))
        for item in sorted(dmi_data[section].keys()):
            print('\t{}: {}'.format(item, dmi_data[section][item]))
        print('\n')

    if retval > 0:
        if retval == 1:
            print("\nFailed 1 test (see above)")
        else:
            print("\nFailed {0} tests (see above)".format(retval))
    else:
        print("\nPassed all tests")

    if bad_data:
        print("\nBad Characters discovered in DMI output. Rerun with "
              "the --show_dmi option to see more")

    return retval


if __name__ == "__main__":
    sys.exit(main())
