#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2014-2018 Canonical Ltd.
# Written by:
#   Daniel Manrique <roadmr@ubuntu.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
manage_compiz_plugin.py
=======================

This script allows enabling or disabling compiz plugins using
gsettings. Changes take effect on the fly.
"""

from gettext import gettext as _
import argparse
import gettext
import os
import subprocess
import time

KEY = "/org/compiz/profiles/unity/plugins/core/active-plugins"

gettext.textdomain("com.canonical.certification.checkbox")
gettext.bindtextdomain("com.canonical.certification.checkbox",
                       os.getenv("CHECKBOX_PROVIDER_LOCALE_DIR", None))

plugins = eval(subprocess.check_output(["dconf", "read", KEY]))

parser = argparse.ArgumentParser(
    description=_("enable/disable compiz plugins"),
    epilog=_("Available plugins: {}").format(plugins))
parser.add_argument("plugin", type=str, help=_('Name of plugin to control'))
parser.add_argument("action", type=str, choices=['enable', 'disable'],
                    help=_("What to do with the plugin"))

args = parser.parse_args()

if args.action == 'enable':
    if args.plugin in plugins:
        raise SystemExit(_("Plugin {} already enabled").format(args.plugin))
    plugins.append(args.plugin)
else:
    if args.plugin not in plugins:
        raise SystemExit(_("Plugin {} doesn't exist").format(args.plugin))
    plugins.remove(args.plugin)
subprocess.call(["dconf", "write", KEY, str(plugins)])

time.sleep(3)
