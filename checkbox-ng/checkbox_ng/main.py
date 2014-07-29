# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
:mod:`checkbox_ng.main` -- entry points for command line tools
==============================================================
"""

import logging

from plainbox.impl.logging import setup_logging

from checkbox_ng.tools import CheckboxLauncherTool
from checkbox_ng.tools import CheckboxServiceTool
from checkbox_ng.tools import CheckboxSubmitTool
from checkbox_ng.tools import CheckboxTool


logger = logging.getLogger("checkbox.ng.main")


def main(argv=None):
    """
    checkbox command line utility
    """
    raise SystemExit(CheckboxTool().main(argv))


def service(argv=None):
    """
    checkbox-service command line utility
    """
    raise SystemExit(CheckboxServiceTool().main(argv))


def submit(argv=None):
    """
    checkbox-submit command line utility
    """
    raise SystemExit(CheckboxSubmitTool().main(argv))


def launcher(argv=None):
    """
    checkbox-launcher command line utility
    """
    raise SystemExit(CheckboxLauncherTool().main(argv))


# Setup logging before anything else starts working.
# If we do it in main() or some other place then unit tests will see
# "leaked" log files which are really closed when the runtime shuts
# down but not when the tests are finishing
setup_logging()
