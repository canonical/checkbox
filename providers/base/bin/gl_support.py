#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
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

import subprocess
import re
import os


class GLSupport:
    """
    This is a simple class to use unity_support_test to verify
    OpenGL is supported or not
    """

    def remove_color_code(self, string: str) -> str:
        """
        Use to make the color code removing could be unit tested

        :param string: the string that you would like to remove color code
        """

        return re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", string)

    def is_support_opengl(self):
        cr = os.getenv("CHECKBOX_RUNTIME", default="")
        cmd = [
            "{}/usr/lib/nux/unity_support_test".format(cr),
            "-p",
        ]
        try:
            rv = subprocess.run(
                cmd,
                universal_newlines=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise SystemExit("running cmd:[{}] fail:{}".format(cmd, repr(e)))
        print(self.remove_color_code(rv.stdout))
        if rv.returncode != 0:
            raise SystemExit("Some OpenGL functions might not be supported")


if __name__ == "__main__":
    GLSupport().is_support_opengl()
