# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
plainbox.impl.test_init
=======================

Test definitions for plainbox.impl module
"""

from unittest import TestCase
import warnings

from plainbox.impl import _get_doc_margin
from plainbox.impl import deprecated


class MiscTests(TestCase):

    def test_get_doc_margin(self):
        self.assertEqual(
            _get_doc_margin(
                "the first line is ignored\n"
                "  subsequent lines"
                "    get counted"
                "  though"),
            2)
        self.assertEqual(
            _get_doc_margin("what if there is no margin?"), 0)


class DeprecatedDecoratorTests(TestCase):
    """
    Tests for the @deprecated function decorator
    """

    def assertWarns(self, warning, callable, *args, **kwds):
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter('always')
            result = callable(*args, **kwds)
            self.assertTrue(any(item.category == warning for item in warning_list))
            return result, warning_list

    def test_func_deprecation_warning(self):
        """
        Ensure that @deprecated decorator makes functions emit deprecation
        warnings on call.
        """
        @deprecated("0.6")
        def func():
            return "value"

        result, warning_list = self.assertWarns(
            DeprecationWarning,
            func,
        )
        self.assertEqual(result, "value")
        # NOTE: we need to use str() as warnings API is a bit silly there
        self.assertEqual(str(warning_list[0].message),
                         'func is deprecated since version 0.6')

    def test_func_docstring(self):
        """
        Ensure that we set or modify the docstring to indicate the fact that
        the function is now deprecated. The original docstring should be
        preserved.
        """

        @deprecated("0.6")
        def func1():
            pass

        @deprecated("0.6")
        def func2():
            """ blah """

        self.assertIn(".. deprecated:: 0.6", func1.__doc__)
        self.assertIn(".. deprecated:: 0.6", func2.__doc__)
        self.assertIn("blah", func2.__doc__)

    def test_common_mistake(self):
        """
        Ensure that we provide a helpful message when a common mistake is made
        """
        with self.assertRaises(SyntaxError) as boom:
            @deprecated
            def func():
                pass
        self.assertEqual(
            str(boom.exception),
            "@deprecated() must be called with a parameter")
