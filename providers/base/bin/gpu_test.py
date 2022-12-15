#!/usr/bin/env python3
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Script checking gpu lockups.

Several threads are started to exercise the GPU in ways that can cause gpu
lockups.
Inspired by the workload directory of the xdiagnose package.
"""

import gi
import os
import re
import subprocess
import sys
import time
gi.require_version('Gio', '2.0')
from gi.repository import Gio  # noqa: E402
from math import cos, sin      # noqa: E402
from threading import Thread   # noqa: E402


class GlxThread(Thread):
    """
    Start a thread running glxgears
    """

    def run(self):

        try:
            self.process = subprocess.Popen(
                ["glxgears", "-geometry", "400x400"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
            self.process.communicate()
        except (subprocess.CalledProcessError, FileNotFoundError) as er:
            print("WARNING: Unable to start glxgears (%s)" % er)

    def terminate(self):
        if not hasattr(self, 'id'):
            print("WARNING: Attempted to terminate non-existing window.")
        if hasattr(self, 'process'):
            self.process.terminate()


class RotateGlxThread(Thread):
    """
    Start a thread performing glxgears windows rotations
    """

    def __init__(self, id, offset):
        Thread.__init__(self)
        self.id = id
        self.offset = offset
        self.cancel = False

    def run(self):
        while True:
            for j in range(60):
                x = int(200 * self.offset + 100 * sin(j * 0.2))
                y = int(200 * self.offset + 100 * cos(j * 0.2))
                coords = "%s,%s" % (x, y)
                subprocess.call(
                    'wmctrl -i -r %s -e 0,%s,-1,-1' % (self.id, coords),
                    shell=True
                )
                time.sleep(0.002 * self.offset)
                if self.cancel:
                    return


class ChangeWorkspace(Thread):
    """
    Start a thread performing fast workspace switches
    """

    def __init__(self, hsize, vsize, xsize, ysize):
        Thread.__init__(self)
        self.hsize = hsize
        self.vsize = vsize
        self.xsize = xsize
        self.ysize = ysize
        self.cancel = False

    def run(self):
        while True:
            for i in range(self.hsize):
                for j in range(self.vsize):
                    subprocess.call(
                        'wmctrl -o %s,%s' % (self.xsize * j, self.ysize * i),
                        shell=True)
                    time.sleep(0.5)
                    if self.cancel:
                        # Switch back to workspace #1
                        subprocess.call('wmctrl -o 0,0', shell=True)
                        return


class Html5VideoThread(Thread):
    """
    Start a thread performing playback of an HTML5 video in firefox
    """

    @property
    def html5_path(self):
        if os.getenv('PLAINBOX_PROVIDER_DATA'):
            return os.path.join(
                os.getenv('PLAINBOX_PROVIDER_DATA'),
                'websites/html5_video.html')

    def run(self):
        if self.html5_path and os.path.isfile(self.html5_path):
            subprocess.call(
                'firefox %s' % self.html5_path,
                stdout=open(os.devnull, 'w'),
                stderr=subprocess.STDOUT,
                shell=True)
        else:
            print("WARNING: unable to start html5 video playback.")
            print("WARNING: test results may be invalid.")

    def terminate(self):
        if self.html5_path and os.path.isfile(self.html5_path):
            subprocess.call("pkill firefox", shell=True)


def check_gpu(log=None):
    if not log:
        log = subprocess.check_output(['dmesg'], universal_newlines=True)
    if re.findall(r'gpu\s+hung', log, flags=re.I):
        print("GPU hung Detected")
        return 1


def main():
    if check_gpu():
        return 1
    GlxWindows = []
    GlxRotate = []
    subprocess.call("pkill 'glxgears|firefox'", shell=True)

    Html5Video = Html5VideoThread()
    Html5Video.start()

    source = Gio.SettingsSchemaSource.get_default()

    for i in range(2):
        GlxWindows.append(GlxThread())
        GlxWindows[i].start()
        time.sleep(5)
        try:
            windows = subprocess.check_output(
                        'wmctrl -l | grep glxgears',
                        shell=True)
        except subprocess.CalledProcessError as er:
            print("WARNING: Got an exception %s" % er)
            windows = ""
        for app in sorted(windows.splitlines(), reverse=True):
            if b'glxgears' not in app:
                continue
            GlxWindows[i].id = str(
                re.match(b'^(0x\w+)', app).group(0), 'utf-8')  # noqa: W605
            break
        if hasattr(GlxWindows[i], "id"):
            rotator = RotateGlxThread(GlxWindows[i].id, i + 1)
            GlxRotate.append(rotator)
            rotator.start()
        else:
            print("WARNING: Window {} not found, not rotating it.".format(i))

    hsize = vsize = 2
    hsize_ori = vsize_ori = None
    if source.lookup("org.compiz.core", True):
        settings = Gio.Settings(
            "org.compiz.core",
            "/org/compiz/profiles/unity/plugins/core/"
        )
        hsize_ori = settings.get_int("hsize")
        vsize_ori = settings.get_int("vsize")
        settings.set_int("hsize", hsize)
        settings.set_int("vsize", vsize)
        time.sleep(5)
    else:
        hsize = int(subprocess.check_output(
            'gconftool --get /apps/compiz-1/general/screen0/options/hsize',
            shell=True))
        vsize = int(subprocess.check_output(
            'gconftool --get /apps/compiz-1/general/screen0/options/vsize',
            shell=True))
    (x_res, y_res) = re.search(
        b'DG:\s+(\d+)x(\d+)',  # noqa: W605
        subprocess.check_output('wmctrl -d', shell=True)).groups()
    DesktopSwitch = ChangeWorkspace(
        hsize, vsize, int(x_res) // hsize, int(y_res) // vsize)
    DesktopSwitch.start()

    time.sleep(35)

    for i in range(len(GlxRotate)):
        GlxRotate[i].cancel = True
    for i in range(len(GlxWindows)):
        GlxWindows[i].terminate()
    DesktopSwitch.cancel = True
    time.sleep(10)
    Html5Video.terminate()
    if check_gpu() or not Html5Video.html5_path:
        return 1

    if source.lookup("org.compiz.core", True):
        settings = Gio.Settings(
            "org.compiz.core",
            "/org/compiz/profiles/unity/plugins/core/")
        settings.set_int("hsize", hsize_ori)
        settings.set_int("vsize", vsize_ori)
        Gio.Settings.sync()


if __name__ == '__main__':
    sys.exit(main())
