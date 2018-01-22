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
:mod:`plainbox.impl.commands.inv_selftest` -- selftest sub-command
==================================================================
"""
import os
import sys
from unittest.loader import defaultTestLoader
from unittest.runner import TextTestRunner


class SelfTestInvocation:

    def __init__(self, loader):
        self.loader = loader

    def run(self, ns):
        # If asked to, re-execute without locale
        if ns.reexec and sys.platform != 'win32':
            self._reexec_without_locale()
        if isinstance(self.loader, str):
            suite = defaultTestLoader.loadTestsFromName(self.loader)
        else:
            suite = self.loader()
        # Use standard unittest runner, it has somewhat annoying way of
        # displaying test progress but is well-known and will do for now.
        runner = TextTestRunner(verbosity=ns.verbosity, failfast=ns.fail_fast)
        result = runner.run(suite)
        # Forward the successfulness of the test suite as the exit code
        return 0 if result.wasSuccessful() else 1

    def _reexec_without_locale(self):
        os.environ['LANG'] = ''
        os.environ['LANGUAGE'] = ''
        os.environ['LC_ALL'] = 'C.UTF-8'
        self_test_index = sys.argv.index('self-test')
        sys.argv.insert(self_test_index + 1, '--after-reexec')
        os.execvpe(sys.argv[0], sys.argv, os.environ)
