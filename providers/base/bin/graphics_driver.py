#!/usr/bin/env python3
# ========================================================================
#
# based on xlogparse
#
# DESCRIPTION
#
# Parses Xlog.*.log format files and allows looking up data from it
#
# AUTHOR
#   Bryce W. Harrington <bryce@canonical.com>
#
# COPYRIGHT
#   Copyright (C) 2010-2012 Bryce W. Harrington
#   All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# ========================================================================
import re
import sys
import os
import glob

from subprocess import Popen, PIPE, check_output, CalledProcessError


class XorgLog(object):

    def __init__(self, logfile=None):
        self.modules = []
        self.errors = []
        self.warnings = []
        self.info = []
        self.notimpl = []
        self.notices = []
        self.cards = []
        self.displays = {}
        self.xserver_version = None
        self.boot_time = None
        self.boot_logfile = None
        self.kernel_version = None
        self.video_driver = None
        self.xorg_conf_path = None
        self.logfile = logfile

        if logfile:
            self.parse(logfile)

    def parse(self, filename):
        self.displays = {}
        display = {}
        display_name = "Unknown"
        in_file = open(filename, errors="ignore")
        gathering_module = False
        found_ddx = False
        module = None
        for line in in_file.readlines():

            # Errors and Warnings
            m = re.search(r"\(WW\) (.*)$", line)
            if m:
                self.warnings.append(m.group(1))
                continue

            m = re.search(r"\(EE\) (.*)$", line)
            if m:
                self.errors.append(m.group(1))
                continue

            # General details
            m = re.search(r"Current Operating System: (.*)$", line)
            if m:
                uname = m.group(1)
                self.kernel_version = uname.split()[2]
                continue

            m = re.search(r"Kernel command line: (.*)$", line)
            if m:
                self.kernel_command_line = m.group(1)
                continue

            m = re.search(r"Build Date: (.*)$", line)
            if m:
                self.kernel_command_line = m.group(1)
                continue

            m = re.search(r'Log file: "(.*)", Time: (.*)$', line)
            if m:
                self.boot_logfile = m.group(1)
                self.boot_time = m.group(2)

            m = re.search(r"xorg-server ([^ ]+) .*$", line)
            if m:
                self.xserver_version = m.group(1)
                continue

            m = re.search(r"Using a default monitor configuration.", line)
            if m and self.xorg_conf_path is None:
                self.xorg_conf_path = "default"
                continue

            m = re.search(r'Using config file: "(.*)"', line)
            if m:
                self.xorg_conf_path = m.group(1)
                continue

            # Driver related information
            m = re.search(r"\(..\)", line)
            if m:
                if gathering_module and module is not None:
                    self.modules.append(module)
                gathering_module = False
                module = None
                m = re.search(
                    r"\(II\) Loading.*modules\/drivers\/(.+)_drv\.so", line
                )
                if m:
                    found_ddx = True
                    continue
                m = re.search(r"\(II\) Module (\w+):", line)
                if m:
                    module = {
                        "name": m.group(1),
                        "vendor": None,
                        "version": None,
                        "class": None,
                        "abi_name": None,
                        "abi_version": None,
                        "ddx": found_ddx,
                    }
                    found_ddx = False
                    gathering_module = True

            if gathering_module:
                m = re.search(r'vendor="(.*:?)"', line)
                if m:
                    module["vendor"] = m.group(1)

                m = re.search(r"module version = (.*)", line)
                if m:
                    module["version"] = m.group(1)

                if module["name"] == "nvidia":
                    try:
                        version = check_output(
                            "nvidia-settings -v",
                            shell=True,
                            universal_newlines=True,
                        )
                        m = re.search(r".*version\s+([0-9\.]+).*", version)
                        if m:
                            module["version"] = m.group(1)
                    except CalledProcessError:
                        pass

                m = re.search(r"class: (.*)", line)
                if m:
                    module["class"] = m.group(1)

                m = re.search(r"ABI class:\s+(.*:?), version\s+(.*:?)", line)
                if m:
                    if m.group(1)[:5] == "X.Org":
                        module["abi_name"] = m.group(1)[6:]
                    else:
                        module["abi_name"] = m.group(1)
                    module["abi_version"] = m.group(2)
                continue

            # EDID and Modelines
            # We use this part to determine which driver is in use
            # For Intel / RADEON / Matrox (using modesetting)
            m = re.search(r"\(II\) (.*)\(\d+\): EDID for output (.*)", line)
            if m:
                self.displays[display_name] = display
                if m.group(1) == "modeset":
                    self.video_driver = "modesetting"
                else:
                    self.video_driver = m.group(1)
                display_name = m.group(2)
                display = {"Output": display_name}
                continue

            m = re.search(
                r"\(II\) (.*)\(\d+\): Assigned Display Device: (.*)$", line
            )
            if m:
                self.displays[display_name] = display
                self.video_driver = m.group(1)
                display_name = m.group(2)
                display = {"Output": display_name}
                continue

            # For NVIDIA
            m = re.search(r'\(II\) (.*)\(\d+\): Setting mode "(.*?):', line)
            if not m:
                m = re.search(
                    r'\(II\) (.*)\(\d+\): Setting mode "(NULL)"', line
                )
            if m:
                self.displays[display_name] = display
                self.video_driver = m.group(1)
                display_name = m.group(2)
                display = {"Output": display_name}
                continue

            # For 4th Intel after 3.11
            m = re.search(
                r"\(II\) (.*)\(\d+\): switch to mode .* using (.*),", line
            )
            if m:
                self.displays[display_name] = display
                self.video_driver = "intel"  # 'intel' is what we expect to see
                display_name = m.group(2)
                display = {"Output": display_name}
                continue

            m = re.search(
                r"Manufacturer: (.*) *Model: (.*) *Serial#: (.*)", line
            )
            if m:
                display["display manufacturer"] = m.group(1)
                display["display model"] = m.group(2)
                display["display serial no."] = m.group(3)

            m = re.search(r"EDID Version: (.*)", line)
            if m:
                display["display edid version"] = m.group(1)

            m = re.search(r"EDID vendor \"(.*)\", prod id (.*)", line)
            if m:
                display["vendor"] = m.group(1)
                display["product id"] = m.group(2)

            m = re.search(
                r"Max Image Size \[(.*)\]: *horiz.: (.*) *vert.: (.*)", line
            )
            if m:
                display["size max horizontal"] = "%s %s" % (
                    m.group(2),
                    m.group(1),
                )
                display["size max vertical"] = "%s %s" % (
                    m.group(3),
                    m.group(1),
                )

            m = re.search(r"Image Size: *(.*) x (.*) (.*)", line)
            if m:
                display["size horizontal"] = "%s %s" % (m.group(1), m.group(3))
                display["size vertical"] = "%s %s" % (m.group(2), m.group(3))

            m = re.search(r"(.*) is preferred mode", line)
            if m:
                display["mode preferred"] = m.group(1)

            m = re.search(r"Modeline \"(\d+)x(\d+)\"x([0-9\.]+) *(.*)$", line)
            if m:
                key = "mode %sx%s@%s" % (m.group(1), m.group(2), m.group(3))
                display[key] = m.group(4)
                continue

        if display_name not in self.displays.keys():
            self.displays[display_name] = display
        in_file.close()

    def errors_filtered(self):
        excludes = set(
            [
                "error, (NI) not implemented, (??) unknown.",
                'Failed to load module "fglrx" (module does not exist, 0)',
                'Failed to load module "nv" (module does not exist, 0)',
            ]
        )
        return [err for err in self.errors if err not in excludes]

    def warnings_filtered(self):
        excludes = set(
            [
                "warning, (EE) error, (NI) not implemented, (??) unknown.",
                'The directory "/usr/share/fonts/X11/cyrillic" does not exist.',  # noqa: E501
                'The directory "/usr/share/fonts/X11/100dpi/" does not exist.',
                'The directory "/usr/share/fonts/X11/75dpi/" does not exist.',
                'The directory "/usr/share/fonts/X11/100dpi" does not exist.',
                'The directory "/usr/share/fonts/X11/75dpi" does not exist.',
                "Warning, couldn't open module nv",
                "Warning, couldn't open module fglrx",
                "Falling back to old probe method for vesa",
                "Falling back to old probe method for fbdev",
            ]
        )
        return [err for err in self.warnings if err not in excludes]


def get_driver_info(xlog):
    """Return the running driver and version"""
    print("-" * 13, "VIDEO DRIVER INFORMATION", "-" * 13)
    if xlog.video_driver:
        for module in xlog.modules:
            if module["name"] == xlog.video_driver.lower():
                print("Video Driver: %s" % module["name"])
                print("Driver Version: %s" % module["version"])
                print("\n")
                return 0
    else:
        print(
            "ERROR: No video driver loaded! Possibly in failsafe mode!",
            file=sys.stderr,
        )
        return 1


def is_laptop():
    return os.path.isdir("/proc/acpi/button/lid")


def hybrid_graphics_check(xlog):
    """Check for Hybrid Graphics"""
    card_id1 = re.compile(r".*0300: *(.+):(.+) \(.+\)")
    card_id2 = re.compile(r".*03..: *(.+):(.+)")
    cards_dict = {"8086": "Intel", "10de": "NVIDIA", "1002": "AMD"}
    cards = []
    drivers = []
    formatted_cards = []

    output = Popen(["lspci", "-n"], stdout=PIPE, universal_newlines=True)
    card_list = output.communicate()[0].split("\n")

    # List of discovered cards
    for line in card_list:
        m1 = card_id1.match(line)
        m2 = card_id2.match(line)
        if m1:
            id1 = m1.group(1).strip().lower()
            id2 = m1.group(2).strip().lower()
            id = id1 + ":" + id2
            cards.append(id)
        elif m2:
            id1 = m2.group(1).strip().lower()
            id2 = m2.group(2).strip().lower()
            id = id1 + ":" + id2
            cards.append(id)

    print("-" * 13, "HYBRID GRAPHICS CHECK", "-" * 16)
    for card in cards:
        formatted_name = cards_dict.get(card.split(":")[0], "Unknown")
        formatted_cards.append(formatted_name)
        print("Graphics Chipset: %s (%s)" % (formatted_name, card))

    for module in xlog.modules:
        if module["ddx"] and module["name"] not in drivers:
            drivers.append(module["name"])
    print("Loaded DDX Drivers: %s" % ", ".join(drivers))

    has_hybrid_graphics = (
        len(cards) > 1
        and is_laptop()
        and (
            cards_dict.get("8086") in formatted_cards
            or cards_dict.get("1002") in formatted_cards
        )
    )

    print("Hybrid Graphics: %s" % (has_hybrid_graphics and "yes" or "no"))

    return 0


def main():
    usr_xorg_dir = os.path.expanduser("~/.local/share/xorg/")
    root_xorg_dir = "/var/log/"
    xlog = None
    xorg_owner = []
    tgt_dir = ""

    # Output the Xorg owner
    xorg_owner = check_output(
        "ps -o user= -p $(pidof Xorg)", shell=True, universal_newlines=True
    ).split()

    # Check the Xorg owner and then judge the Xorg log location
    if "root" in xorg_owner:
        tgt_dir = root_xorg_dir
    elif xorg_owner:
        tgt_dir = usr_xorg_dir
    else:
        print("ERROR: No Xorg process found!", file=sys.stderr)

    if tgt_dir:
        xorg_file_paths = list(glob.iglob(tgt_dir + "Xorg.*.log"))
        target_file = xorg_file_paths[0]
        xlog = XorgLog(target_file)

    results = []

    results.append(get_driver_info(xlog))
    results.append(hybrid_graphics_check(xlog))

    return 1 if 1 in results else 0


if __name__ == "__main__":
    sys.exit(main())
