# This file is part of Checkbox.
#
# Copyright 2019 Canonical Ltd.
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
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

import importlib.util
import os


def main():
    manage_f = os.path.join(os.getcwd(), 'manage.py')
    if not os.path.exists(manage_f):
        raise SystemExit('Could not find manage.py in current directory.'
                         ' Is this a plainbox provider?')
    spec = importlib.util.spec_from_file_location('setup', manage_f)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)
