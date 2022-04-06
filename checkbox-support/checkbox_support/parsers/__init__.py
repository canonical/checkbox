# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
"""
This module provides an entry point to checkbox-support-parse.

The commands turns an output of system commands and turns them into json.
When a new parser is added, it should be added to AVAILABLE_PARSER mapping."
"""

import io
import json
import re
import sys

from argparse import ArgumentParser

from checkbox_support.parsers import dkms_info
from checkbox_support.parsers import dmidecode
from checkbox_support.parsers import image_info
from checkbox_support.parsers import kernel_cmdline
from checkbox_support.parsers import modinfo
from checkbox_support.parsers import modprobe
from checkbox_support.parsers import pactl
from checkbox_support.parsers import pci_config
from checkbox_support.parsers import udevadm

AVAILABLE_PARSERS = {
    'bto': image_info.parse_bto_attachment_output,
    'buildstamp': image_info.parse_buildstamp_attachment_output,
    'dkms-info': dkms_info.parse_dkms_info,
    'dmidecode': dmidecode.parse_dmidecode_output,
    'kernelcmdline': kernel_cmdline.parse_kernel_cmdline,
    'modinfo': modinfo.parse_modinfo_attachment_output,
    'modprobe': modprobe.parse_modprobe_d_output,
    'pactl-list': pactl.parse_pactl_output,
    'pci-subsys-id': pci_config.parse_pci_subsys_id,
    'recovery-info': image_info.parse_recovery_info_attachment_output,
    'udevadm': udevadm.parse_udevadm_output,
}
PARSER_LIST = sorted(list(AVAILABLE_PARSERS.keys()))
Pattern = type(re.compile(""))


def main():
    """Entry point to the program."""
    arg_parser = ArgumentParser(
        description="parse stdin with the specified parser")
    arg_parser.add_argument(
        "parser_name", metavar="PARSER-NAME",
        choices=['?'] + PARSER_LIST,
        help="Name of the parser to use")
    args = arg_parser.parse_args()
    if args.parser_name == '?':
        print("The following parsers are available:")
        print("\n".join(PARSER_LIST))
        raise SystemExit()
    parser = AVAILABLE_PARSERS[args.parser_name]
    stdin = sys.stdin
    with io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8') as stdin:
        try:
            text = stdin.read()
            print(run_parsing(parser, text))
        except UnicodeDecodeError as exc:
            msg = "Failed to decode input stream: {}".format(str(exc))
            raise SystemExit(msg) from exc


def run_parsing(parser_fn, text):
    """Do the actual parsing."""
    try:
        ast = parser_fn(text)
        return json.dumps(
            ast, indent=4, sort_keys=True, default=_json_fallback)
    except Exception as exc:
        msg = "Failed to parse the text: {}".format(str(exc))
        raise SystemExit(msg) from exc


def _json_fallback(obj):
    """
    Helper method to convert arbitrary objects to their JSON
    representation.

    Anything that has a 'as_json' attribute will be converted to the result
    of calling that method. For all other objects __dict__ is returned.
    """
    if isinstance(obj, Pattern):
        return "<Pattern>"
    if hasattr(obj, "as_json"):
        return obj.as_json()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    if hasattr(obj, "__slots__"):
        return {slot: getattr(obj, slot) for slot in obj.__slots__}
    raise NotImplementedError(
        "unable to json-ify {!r}".format(obj.__class__))
