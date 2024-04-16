# This file is part of Checkbox.
#
# Copyright 2013-2015 Canonical Ltd.
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
:mod:`plainbox.impl.parsers` -- generic parser interface
========================================================

This module offers high-level API for parsing text into hierarchical
data structures, in particular, JSON. Parsers like this can be used
to create abstract syntax trees of compatible inputs. For convenience
and scriptability any parser is expected to be able to dump its AST
as JSON.
"""
import abc
import inspect
import json
import logging
import re

from plainbox.i18n import gettext as _
from plainbox.impl.secure.plugins import PkgResourcesPlugInCollection, PlugIn


logger = logging.getLogger("plainbox.parsers")


Pattern = type(re.compile(""))


class IParser(metaclass=abc.ABCMeta):
    """
    Abstract interface for parsers.

    The interface is meant to be suitable for the implementation of the
    `plainbox dev parse` command. It offers a simple API for parsing strings
    and getting JSON in result.
    """

    @abc.abstractproperty
    def name(self):
        """
        name of the parser
        """

    @abc.abstractproperty
    def summary(self):
        """
        one-line description of the parser
        """

    @abc.abstractmethod
    def parse_text_to_ast(self, text):
        """
        Parse the specified text and return a parser-specific native Abstract
        Syntax Tree that represents the input.

        Any exception gets logged and causes None to be returned.
        """

    @abc.abstractmethod
    def parse_text_to_json(self, text):
        """
        Parse the specified text and return a JSON string representing the
        result.

        :returns: None in case of parse error
        :returns: string representing JSON version of the parsed AST
        """


class ParserPlugIn(IParser, PlugIn):
    """
    PlugIn wrapping a parser function.

    Useful for wrapping checkbox parser functions.
    """

    @property
    def name(self):
        """
        name of the parser
        """
        return self.plugin_name

    @property
    def parser_fn(self):
        """
        real parser function
        """
        return self.plugin_object

    @property
    def summary(self):
        """
        one-line description of the parser

        This value is computed from the docstring of the wrapped function.
        In fact, it is the fist line of the docstring.
        """
        return inspect.getdoc(self.parser_fn).split("\n", 1)[0]

    def parse_text_to_json(self, text):
        """
        Parse the specified text and return a JSON string representing the
        result.

        :returns: None in case of parse error
        :returns: string representing JSON version of the parsed AST
        """
        ast = self.parse_text_to_ast(text)
        if ast is not None:
            return json.dumps(
                ast, indent=4, sort_keys=True, default=self._to_json
            )

    def parse_text_to_ast(self, text):
        """
        Parse the specified text and return a parser-specific native Abstract
        Syntax Tree that represents the input.

        Any exception gets logged and causes None to be returned.
        """
        try:
            return self.parser_fn(text)
        except Exception:
            # TODO: portable parser error would be nice, to know where it
            # fails. This is difficult at this stage.

            logger.exception(_("Cannot parse input"))
            return None

    def _to_json(self, obj):
        """
        Helper method to convert arbitrary objects to their JSON
        representation.

        Anything that has a 'as_json' attribute will be converted to the result
        of calling that method. For all other objects __dict__ is returned.
        """
        if isinstance(obj, Pattern):
            return "<Pattern>"
        elif hasattr(obj, "as_json"):
            return obj.as_json()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        elif hasattr(obj, "__slots__"):
            return {slot: getattr(obj, slot) for slot in obj.__slots__}
        else:
            raise NotImplementedError(
                "unable to json-ify {!r}".format(obj.__class__)
            )


# Collection of all parsers
all_parsers = PkgResourcesPlugInCollection(
    "plainbox.parsers", wrapper=ParserPlugIn
)
