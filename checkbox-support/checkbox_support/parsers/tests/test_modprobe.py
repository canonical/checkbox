# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from io import StringIO
from unittest import TestCase

from checkbox_support.parsers.modprobe import ModprobeParser

MODPROBE1 = """\
options bogus_mod param=1
"""

MODPROBE2 = """\
options bogus_mod setting=pakistan
options phony_mod chop=450
options bogus_mod param=1
"""

MODPROBE3 = """\
# Introduces some bogus crap like comments
options bogus_mod   param=1
options bogus_mod setting=pakistan
options bogus_mod param=1    setting=pakistan
options   phony_mod chop=450
blacklist my-module  # And a module blacklist. BTW, inline comments are
# NOT supported by the modprobe spec, so this is even more evil input.
"""


class ModprobeResult():

    def __init__(self):
        self.mod_options = {}

    def addModprobeInfo(self, module, options):
        self.mod_options[module] = options

class TestModprobeParser(TestCase):

    def test_single_module_option(self):
        """
        Test that a module that appears only once with only one option
        is correctly parsed
        """

        stream = StringIO(MODPROBE1)
        self.parser = ModprobeParser(stream)
        result = ModprobeResult()
        self.parser.run(result)
        self.assertIn("bogus_mod", result.mod_options)
        self.assertEqual(result.mod_options['bogus_mod'], "param=1")

    def test_nice_input(self):
        """
        Test correct parsing on a simple file with nice, tidy input
        """
        self._module_multiple_instances(MODPROBE2)
        self._multiple_modules(MODPROBE2)

    def test_trickier_input(self):
        """
        Test correct parsing on a file with weirder syntax.
        * It includes comments.
        * It includes different stuff like blacklist which we should
          ignore
        * Spacing of options lines is weird (test whitespace handling)
        """
        self._module_multiple_instances(MODPROBE3)
        self._multiple_modules(MODPROBE3)

    def _module_multiple_instances(self, data):
        """
        Test that options for the same module on multiple lines are
        correctly aggregated/deduped

        :param data: A stream for the parser to process.
        """

        stream = StringIO(data)
        self.parser = ModprobeParser(stream)
        result = ModprobeResult()
        self.parser.run(result)
        self.assertIn("bogus_mod", result.mod_options)
        # Ensure each expected param appears, but only once
        # since the parser should squash dupes
        for param in ["param=1", "setting=pakistan"]:
            self.assertEqual(1, result.mod_options['bogus_mod'].count(param),
                    result.mod_options['bogus_mod'])

    def _multiple_modules(self, data):
        """
        Test that different modules in the same input are correctly
        processed

        :param data: A stream for the parser to process.
        """

        stream = StringIO(data)
        self.parser = ModprobeParser(stream)
        result = ModprobeResult()
        self.parser.run(result)
        self.assertIn("bogus_mod", result.mod_options)
        self.assertIn("phony_mod", result.mod_options)
        self.assertEqual(result.mod_options['phony_mod'], "chop=450")
