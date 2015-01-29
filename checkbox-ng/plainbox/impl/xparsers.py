# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
:mod:`plainbox.impl.xparsers` -- parsers for various plainbox formats
=====================================================================

This module contains parsers for several formats that plainbox has to deal
with. They are not real parsers (as they can be handled with simple regular
expressions most of the time) but rather simple top-down parsing snippets
spread around some classes.

What is interesting though, is the set of classes and their relationships (and
attributes) as that helps to work with the code.


Node and Visitor
----------------
The basic class for everything parsed is :class:`Node`. It contains two
attributes, :attr:`Node.lineno` and :attr:`Node.col_offset` (mimicking the
python AST) and a similar, but not identical visitor mechanism. The precise way
in which the visitor class operates is documented on :class:`Visitor`. In
general application code can freely explore (but not modify as everything is
strictly read-only) the AST.

Regular expressions
-------------------
We have to deal with regular expressions in many places so there's a dedicated
AST node for handling them. The root class is :class:`Re` but it's just a base
for one of the three concrete sub-classes :class:`ReErr`, :class:`ReFixed` and
:class:`RePattern`. ``ReErr`` is an error wrapper (when the regular expression
is incorrect and doesn't work) and the other two (which also share a common
base class :class:`ReOk`) can be used to do text matching. Since other parts of
the code already contain optimizations for regular expressions that are just a
plain string comparison there is a special class to highlight that fact
(``ReFixed``)

White Lists
-----------
White lists are a poor man's test plan which describes a list of regular
expressions with optional comments. The root class is :class:`WhiteList` who's
:attr:`WhiteList.entries` attribute contains a sequence of either
:class:`Comment` or a subclass of :class:`Re`.
"""
import abc
import re
import sre_constants
import sre_parse

from plainbox.impl import pod
from plainbox.impl.censoREd import PatternProxy

__all__ = [
    'Comment',
    'Node',
    'Re',
    'ReErr',
    'ReFixed',
    'ReOk',
    'RePattern',
    'Visitor',
    'WhiteList',
]

Pattern = type(re.compile(""))

afn_typed_const = (pod.typed, pod.const)


def F(doc, type, initial_fn=None):
    """ shortcut for creating fields """
    if type is list:
        return pod.Field(
            doc, type, initial_fn=type,
            assign_filter_list=afn_typed_const)
    else:
        return pod.Field(
            doc, type, pod.MANDATORY,
            assign_filter_list=afn_typed_const)


@pod.modify_field_docstring("not negative")
def not_negative(
    instance: pod.POD, field: pod.Field, old: "Any", new: "Any"
) -> "Any":
    if new < 0:
        raise ValueError("{}.{} cannot be negative".format(
            instance.__class__.__name__, field.name, field.type.__name__))
    return new


class Node(pod.POD):
    """ base node type """
    lineno = pod.Field(
        "Line number (1-based)", int, 0,
        assign_filter_list=[pod.typed, not_negative, pod.const])
    col_offset = pod.Field(
        "Column offset (0-based)", int, 0,
        assign_filter_list=[pod.typed, not_negative, pod.const])

    def visit(self, visitor: 'Visitor'):
        """
        Visit all of the sub-nodes reachable from this node

        :param visitor:
            Visitor object that gets to explore this and all the other nodes
        :returns:
            The return value of the visitor's :meth:`Visitor.visit()` method,
            if any.  The default visitor doesn't return anything.

        """
        return visitor.visit(self)

    def enumerate_entries(self) -> "Generator[node]":
        for field in self.__class__.field_list:
            obj = field.__get__(self, self.__class__)
            if isinstance(obj, Node):
                yield obj
            elif isinstance(obj, list):
                for list_item in obj:
                    if isinstance(list_item, Node):
                        yield list_item


class Visitor:
    """
    Class assisting in traversing :class:`Node` trees.

    This class can be used to explore the AST of any of the plainbox-parsed
    text formats. The way to use this method is to create a custom sub-class of
    the :class:`Visitor` class and to define methods that correspond to the
    class of node one is interested in.

    Example:
    >>> class Text(Node):
    ...     text = F("text", str)

    >>> class Group(Node):
    ...     items = F("items", list)

    >>> class demo_visitor(Visitor):
    ...     def visit_Text_node(self, node: Text):
    ...         print("visiting text node: {}".format(node.text))
    ...         return self.generic_visit(node)
    ...     def visit_Group_node(self, node: Group):
    ...         print("visiting list node")
    ...         return self.generic_visit(node)

    >>> Group(items=[
    ...     Text(text="foo"), Text(text="bar")
    ... ]).visit(demo_visitor())
    visiting list node
    visiting text node: foo
    visiting text node: bar
    """

    def generic_visit(self, node: Node) -> None:
        """ visit method called on nodes without a dedicated visit method"""
        # XXX: I don't love the way this works, perhaps we should be less smart
        # and just require implicit hints as to where to go? Perhaps children
        # should be something that any node can carry?
        for child_node in node.enumerate_entries():
            self.visit(child_node)

    def visit(self, node: Node) -> "Any":
        """ visit the specified node """
        node_name = node.__class__.__name__
        visit_meth_name = 'visit_{}_node'.format(node_name)
        if hasattr(self, visit_meth_name):
            visit_meth = getattr(self, visit_meth_name)
            return visit_meth(node)
        else:
            return self.generic_visit(node)


class Re(Node):
    """ node representing a regular expression """
    text = F("Text of the regular expression (perhaps invalid)", str)

    @staticmethod
    def parse(text: str, lineno: int=0, col_offset: int=0) -> "Re":
        """
        Parse a bit of text and return a concrete subclass of ``Re``

        :param text:
            The text to parse
        :returns:
            If ``text`` is a correct regular expression then an instance of
            :class:`ReOk` is returned. In practice exactly one of
            :class:`ReFixed` or :class:`RePattern` may be returned.
            If ``text`` is incorrect then an instance of :class:`ReErr` is
            returned.

        Examples:

        >>> Re.parse("text")
        ReFixed(lineno=0, col_offset=0, text='text')

        >>> Re.parse("pa[tT]ern") # doctest: +NORMALIZE_WHITESPACE
        RePattern(lineno=0, col_offset=0, text='pa[tT]ern',
                  re=re.compile('pa[tT]ern'))

        >>> from sre_constants import error
        >>> Re.parse("+")  # doctest: +NORMALIZE_WHITESPACE
        ReErr(lineno=0, col_offset=0, text='+',
              exc=error('nothing to repeat',))
        """
        try:
            pyre_ast = sre_parse.parse(text)
        except sre_constants.error as exc:
            return ReErr(lineno, col_offset, text, exc)
        else:
            # Check if the AST of this regular expression is composed
            # of just a flat list of 'literal' nodes. In other words,
            # check if it is a simple string match in disguise
            if all(t == 'literal' for t, rest in pyre_ast):
                return ReFixed(lineno, col_offset, text)
            else:
                # NOTE: we might save time by calling some internal function to
                # convert pyre_ast to the pattern object.
                #
                # XXX: The actual compiled pattern is wrapped in PatternProxy
                # to ensure that it can be repr()'ed sensibly on Python 3.2
                return RePattern(
                    lineno, col_offset, text, PatternProxy(re.compile(text)))


class ReOk(Re):
    """ node representing a correct regular expression """

    @abc.abstractmethod
    def match(self, text: str) -> bool:
        """
        check if the given text matches the expression

        This method is provided by all of the subclasses of
        :class:`ReOk`, sometimes the implementation is faster than a
        naive regular expression match.

        >>> Re.parse("foo").match("foo")
        True

        >>> Re.parse("foo").match("f")
        False

        >>> Re.parse("[fF]oo").match("foo")
        True

        >>> Re.parse("[fF]oo").match("Foo")
        True
        """


class ReFixed(ReOk):
    """ node representing a trivial regular expression (fixed string)"""

    def match(self, text: str) -> bool:
        return text == self.text


class RePattern(ReOk):
    """ node representing a regular expression pattern """
    re = F("regular expression object", Pattern)

    def match(self, text: str) -> bool:
        return self.re.match(text) is not None


class ReErr(Re):
    """ node representing an incorrect regular expression """
    exc = F("exception describing the problem", Exception)


class Comment(Node):
    """ node representing single comment """
    comment = F("comment text, including any comment markers", str)


class WhiteList(Node):
    """ node representing a whole plainbox whitelist """

    entries = pod.Field("a list of comments and patterns", list,
                        initial_fn=list, assign_filter_list=[
                            pod.typed, pod.typed.sequence(Node), pod.const])

    @staticmethod
    def parse(text: str, lineno: int=1, col_offset: int=0) -> "WhiteList":
        """
        Parse a plainbox *whitelist*

        Empty string is still a valid (though empty) whitelist

        >>> WhiteList.parse("")
        WhiteList(lineno=1, col_offset=0, entries=[])

        White space is irrelevant and gets ignored if it's not of any
        semantic value. Since whitespace was never a part of the de-facto
        allowed pattern syntax one cannot create a job with " ".

        >>> WhiteList.parse("   ")
        WhiteList(lineno=1, col_offset=0, entries=[])

        As soon as there's something interesting though, it starts to have
        meaning. Note that we differentiate the raw text ' a ' from the
        pattern object is represents '^namespace::a$' but at this time,
        when we parse the text this contextual, semantic information is not
        available and is not a part of the AST.

        >>> WhiteList.parse(" data ") # doctest: +NORMALIZE_WHITESPACE
        WhiteList(lineno=1, col_offset=0,
                  entries=[ReFixed(lineno=1, col_offset=0, text=' data ')])

        Data gets separated into line-based records.  Any number of lines
        may exist in a single whitelist.

        >>> WhiteList.parse("line") # doctest: +NORMALIZE_WHITESPACE
        WhiteList(lineno=1, col_offset=0,
                  entries=[ReFixed(lineno=1, col_offset=0, text='line')])

        >>> WhiteList.parse("line 1\\nline 2\\n")
        ... # doctest: +NORMALIZE_WHITESPACE
        WhiteList(lineno=1, col_offset=0,
                  entries=[ReFixed(lineno=1, col_offset=0, text='line 1'),
                           ReFixed(lineno=2, col_offset=0, text='line 2')])

        Empty lines are just ignored. You can re-create them by observing lack
        of continuity in the values of the ``lineno`` field.

        >>> WhiteList.parse("line 1\\n\\nline 3\\n")
        ... # doctest: +NORMALIZE_WHITESPACE
        WhiteList(lineno=1, col_offset=0,
                  entries=[ReFixed(lineno=1, col_offset=0, text='line 1'),
                           ReFixed(lineno=3, col_offset=0, text='line 3')])

        Data can be mixed with comments. Note that col_offset is finally
        non-zero here as the comments starts on the fourth character into the
        line:

        >>> WhiteList.parse("foo # pick foo")
        ... # doctest: +NORMALIZE_WHITESPACE
        WhiteList(lineno=1, col_offset=0,
                  entries=[ReFixed(lineno=1, col_offset=0, text='foo '),
                           Comment(lineno=1, col_offset=4,
                                   comment='# pick foo')])

        Comments can also exist without any data:

        >>> WhiteList.parse("# this is a comment")
        ... # doctest: +NORMALIZE_WHITESPACE, +ELLIPSIS
        WhiteList(lineno=1, col_offset=0,
                  entries=[Comment(lineno=1, col_offset=0,
                                   comment='# this ...')])

        Lastly, there are no *exceptions* at this stage, broken patterns are
        represented as such but no exceptions are ever raised:

        >>> WhiteList.parse("[]")
        ... # doctest: +NORMALIZE_WHITESPACE, +ELLIPSIS
        WhiteList(lineno=1, col_offset=0,
                  entries=[ReErr(lineno=1, col_offset=0, text='[]',
                                 exc=error('un...',))])
        """
        entries = []
        initial_lineno = lineno
        # NOTE: lineno is consciously shadowed below
        for lineno, line in enumerate(text.splitlines(), lineno):
            if '#' in line:
                cindex = line.index('#')
                comment = line[cindex:]
                data = line[:cindex]
            else:
                cindex = None
                comment = None
                data = line
            if not data.strip():
                data = None
            if data:
                entries.append(Re.parse(data, lineno, col_offset))
            if comment:
                entries.append(Comment(lineno, col_offset + cindex, comment))
        return WhiteList(initial_lineno, col_offset, entries)
