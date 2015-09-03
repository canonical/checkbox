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
import itertools
import re
import sre_constants
import sre_parse
import sys

from plainbox.i18n import gettext as _
from plainbox.impl import pod
from plainbox.impl.censoREd import PatternProxy
from plainbox.impl.xscanners import WordScanner

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

    def __repr__(self):
        return "{}({})".format(
            self.__class__.__name__,
            ', '.join([
                '{}={!r}'.format(field.name, getattr(self, field.name))
                for field in self.__class__.field_list
                if field.name not in ('lineno', 'col_offset')]))

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
        ReFixed(text='text')

        >>> Re.parse("pa[tT]ern")
        RePattern(text='pa[tT]ern', re=re.compile('pa[tT]ern'))

        >>> from sre_constants import error
        >>> Re.parse("+")
        ReErr(text='+', exc=error('nothing to repeat',))
        """
        try:
            pyre_ast = sre_parse.parse(text)
        except sre_constants.error as exc:
            assert len(exc.args) == 1
            # XXX: This is a bit crazy but this lets us have identical error
            # messages across python3.2 all the way to 3.5. I really really
            # wish there was a better way at fixing this.
            exc.args = (re.sub(" at position \d+", "", exc.args[0]), )
            return ReErr(lineno, col_offset, text, exc)
        else:
            # Check if the AST of this regular expression is composed
            # of just a flat list of 'literal' nodes. In other words,
            # check if it is a simple string match in disguise
            if ((sys.version_info[:2] >= (3, 5) and
                    all(t == sre_constants.LITERAL for t, rest in pyre_ast)) or
                    all(t == 'literal' for t, rest in pyre_ast)):
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
        WhiteList(entries=[])

        White space is irrelevant and gets ignored if it's not of any
        semantic value. Since whitespace was never a part of the de-facto
        allowed pattern syntax one cannot create a job with " ".

        >>> WhiteList.parse("   ")
        WhiteList(entries=[])

        As soon as there's something interesting though, it starts to have
        meaning. Note that we differentiate the raw text ' a ' from the
        pattern object is represents '^namespace::a$' but at this time,
        when we parse the text this contextual, semantic information is not
        available and is not a part of the AST.

        >>> WhiteList.parse(" data ")
        WhiteList(entries=[ReFixed(text=' data ')])

        Data gets separated into line-based records.  Any number of lines
        may exist in a single whitelist.

        >>> WhiteList.parse("line")
        WhiteList(entries=[ReFixed(text='line')])

        >>> WhiteList.parse("line 1\\nline 2\\n")
        WhiteList(entries=[ReFixed(text='line 1'), ReFixed(text='line 2')])

        Empty lines are just ignored. You can re-create them by observing lack
        of continuity in the values of the ``lineno`` field.

        >>> WhiteList.parse("line 1\\n\\nline 3\\n")
        WhiteList(entries=[ReFixed(text='line 1'), ReFixed(text='line 3')])

        Data can be mixed with comments. Note that col_offset is finally
        non-zero here as the comments starts on the fourth character into the
        line:

        >>> WhiteList.parse("foo # pick foo")
        ... # doctest: +NORMALIZE_WHITESPACE
        WhiteList(entries=[ReFixed(text='foo '),
                           Comment(comment='# pick foo')])

        Comments can also exist without any data:

        >>> WhiteList.parse("# this is a comment")
        WhiteList(entries=[Comment(comment='# this is a comment')])

        Lastly, there are no *exceptions* at this stage, broken patterns are
        represented as such but no exceptions are ever raised:

        >>> WhiteList.parse("[]")
        ... # doctest: +ELLIPSIS
        WhiteList(entries=[ReErr(text='[]', exc=error('un...',))])
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


class Error(Node):
    """ node representing a syntax error """
    msg = F("message", str)


class Text(Node):
    """ node representing a bit of text """
    text = F("text", str)


class FieldOverride(Node):
    """ node representing a single override statement """

    value = F("value to apply (override value)", Text)
    pattern = F("pattern that selects things to override", Re)

    @staticmethod
    def parse(
        text: str, lineno: int=1, col_offset: int=0
    ) -> "Union[FieldOverride, Error]":
        """
        Parse a single test plan field override line

        Using correct syntax will result in a FieldOverride node with
        appropriate data in the ``value`` and ``pattern`` fields. Note that
        ``pattern`` may be either a :class:`RePattern` or a :class:`ReFixed` or
        :class:`ReErr` which is not a valid pattern and cannot be used.

            >>> FieldOverride.parse("apply new-value to pattern")
            ... # doctest: +NORMALIZE_WHITESPACE
            FieldOverride(value=Text(text='new-value'),
                          pattern=ReFixed(text='pattern'))
            >>> FieldOverride.parse("apply blocker to .*")
            ... # doctest: +NORMALIZE_WHITESPACE
            FieldOverride(value=Text(text='blocker'),
                          pattern=RePattern(text='.*', re=re.compile('.*')))

        Using incorrect syntax will result in a single Error node being
        returned. The message (``msg``) field contains useful information on
        the cause of the problem, as depicted below:

            >>> FieldOverride.parse("")
            Error(msg="expected 'apply' near ''")
            >>> FieldOverride.parse("apply")
            Error(msg='expected override value')
            >>> FieldOverride.parse("apply value")
            Error(msg="expected 'to' near ''")
            >>> FieldOverride.parse("apply value to")
            Error(msg='expected override pattern')
            >>> FieldOverride.parse("apply value to pattern junk")
            Error(msg="unexpected garbage: 'junk'")

        Lastly, shell-style comments are supported. They are discarded by the
        scanner code though.

            >>> FieldOverride.parse("apply value to pattern # comment")
            ... # doctest: +NORMALIZE_WHITESPACE
            FieldOverride(value=Text(text='value'),
                          pattern=ReFixed(text='pattern'))

        """
        # XXX  Until our home-grown scanner is ready col_offset values below
        # are all dummy. This is not strictly critical but should be improved
        # upon later.
        scanner = WordScanner(text)
        # 'APPLY' ...
        token, lexeme = scanner.get_token()
        if token != scanner.TokenEnum.WORD or lexeme != 'apply':
            return Error(lineno, col_offset,
                         _("expected {!a} near {!r}").format('apply', lexeme))
        # 'APPLY' VALUE ...
        token, lexeme = scanner.get_token()
        if token != scanner.TokenEnum.WORD:
            return Error(lineno, col_offset, _("expected override value"))
        value = Text(lineno, col_offset, lexeme)
        # 'APPLY' VALUE 'TO' ...
        token, lexeme = scanner.get_token()
        if token != scanner.TokenEnum.WORD or lexeme != 'to':
            return Error(lineno, col_offset,
                         _("expected {!a} near {!r}").format('to', lexeme))
        # 'APPLY' VALUE 'TO' PATTERN...
        token, lexeme = scanner.get_token()
        if token != scanner.TokenEnum.WORD:
            return Error(lineno, col_offset, _("expected override pattern"))
        pattern = Re.parse(lexeme, lineno, col_offset)
        # 'APPLY' VALUE 'TO' PATTERN <EOF>
        token, lexeme = scanner.get_token()
        if token != scanner.TokenEnum.EOF:
            return Error(lineno, col_offset,
                         _("unexpected garbage: {!r}").format(lexeme))
        return FieldOverride(lineno, col_offset, value, pattern)


class OverrideFieldList(Node):
    """ node representing a whole plainbox field override list"""

    entries = pod.Field("a list of comments and patterns", list,
                        initial_fn=list, assign_filter_list=[
                            pod.typed, pod.typed.sequence(Node), pod.const])

    @staticmethod
    def parse(
        text: str, lineno: int=1, col_offset: int=0
    ) -> "OverrideFieldList":
        entries = []
        initial_lineno = lineno
        # NOTE: lineno is consciously shadowed below
        for lineno, line in enumerate(text.splitlines(), lineno):
            entries.append(FieldOverride.parse(line, lineno, col_offset))
        return OverrideFieldList(initial_lineno, col_offset, entries)


class OverrideExpression(Node):
    """ node representing a single override statement """

    field = F("field to override", Text)
    value = F("value to apply", Text)


class IncludeStmt(Node):
    """ node representing a single include statement """

    pattern = F("the pattern used for selecting jobs", Re)
    overrides = pod.Field("list of overrides to apply", list, initial_fn=list,
                          assign_filter_list=[
                              pod.typed,
                              pod.typed.sequence(OverrideExpression),
                              pod.const])

    @staticmethod
    def parse(
        text: str, lineno: int=1, col_offset: int=0
    ) -> "Union[IncludeStmt, Error]":
        """
        Parse a single test plan include line

        Using correct syntax will result in a IncludeStmt node with
        appropriate data in the ``pattern`` and ``overrides`` fields. Note that
        ``pattern`` may be either a :class:`RePattern` or a :class:`ReFixed` or
        :class:`ReErr` which is not a valid pattern and cannot be used.
        Overrides are a list of :class:`OverrideExpression`. The list may
        contain incorrect, or duplicate values but that's up to higher-level
        analysis to check for.

        The whole overrides section is optional so a single pattern is a good
        include statement:

            >>> IncludeStmt.parse("usb.*")
            ... # doctest: +NORMALIZE_WHITESPACE
            IncludeStmt(pattern=RePattern(text='usb.*',
                                          re=re.compile('usb.*')),
                        overrides=[])

        Any number of key=value override pairs can be used using commas in
        between each pair:

            >>> IncludeStmt.parse("usb.* f1=o1")
            ... # doctest: +NORMALIZE_WHITESPACE
            IncludeStmt(pattern=RePattern(text='usb.*',
                                          re=re.compile('usb.*')),
                        overrides=[OverrideExpression(field=Text(text='f1'),
                                                      value=Text(text='o1'))])
            >>> IncludeStmt.parse("usb.* f1=o1, f2=o2")
            ... # doctest: +NORMALIZE_WHITESPACE
            IncludeStmt(pattern=RePattern(text='usb.*',
                                          re=re.compile('usb.*')),
                        overrides=[OverrideExpression(field=Text(text='f1'),
                                                      value=Text(text='o1')),
                                   OverrideExpression(field=Text(text='f2'),
                                                      value=Text(text='o2'))])
            >>> IncludeStmt.parse("usb.* f1=o1, f2=o2, f3=o3")
            ... # doctest: +NORMALIZE_WHITESPACE
            IncludeStmt(pattern=RePattern(text='usb.*',
                                          re=re.compile('usb.*')),
                        overrides=[OverrideExpression(field=Text(text='f1'),
                                                      value=Text(text='o1')),
                                   OverrideExpression(field=Text(text='f2'),
                                                      value=Text(text='o2')),
                                   OverrideExpression(field=Text(text='f3'),
                                                      value=Text(text='o3'))])

        Obviously some things can fail, the following examples show various
        error states that are possible. In each state an Error node is returned
        instead of the whole statement.

            >>> IncludeStmt.parse("")
            Error(msg='expected pattern')
            >>> IncludeStmt.parse("pattern field")
            Error(msg="expected '='")
            >>> IncludeStmt.parse("pattern field=")
            Error(msg='expected override value')
            >>> IncludeStmt.parse("pattern field=override junk")
            Error(msg="expected ','")
            >>> IncludeStmt.parse("pattern field=override, ")
            Error(msg='expected override field')
        """
        scanner = WordScanner(text)
        # PATTERN ...
        token, lexeme = scanner.get_token()
        if token != scanner.TokenEnum.WORD:
            return Error(lineno, col_offset, _("expected pattern"))
        pattern = Re.parse(lexeme, lineno, col_offset)
        overrides = []
        for i in itertools.count():
            # PATTERN FIELD ...
            token, lexeme = scanner.get_token()
            if token == scanner.TokenEnum.EOF and i == 0:
                # The whole override section is optional so the sequence may
                # end with EOF on the first iteration of the loop.
                break
            elif token != scanner.TokenEnum.WORD:
                return Error(lineno, col_offset, _("expected override field"))
            field = Text(lineno, col_offset, lexeme)
            # PATTERN FIELD = ...
            token, lexeme = scanner.get_token()
            if token != scanner.TokenEnum.EQUALS:
                return Error(lineno, col_offset, _("expected '='"))
            # PATTERN FIELD = VALUE ...
            token, lexeme = scanner.get_token()
            if token != scanner.TokenEnum.WORD:
                return Error(lineno, col_offset, _("expected override value"))
            value = Text(lineno, col_offset, lexeme)
            expr = OverrideExpression(lineno, col_offset, field, value)
            overrides.append(expr)
            # is there any more?
            # PATTERN FIELD = VALUE , ...
            token, lexeme = scanner.get_token()
            if token == scanner.TokenEnum.COMMA:
                # (and again)
                continue
            elif token == scanner.TokenEnum.EOF:
                break
            else:
                return Error(lineno, col_offset, _("expected ','"))
        return IncludeStmt(lineno, col_offset, pattern, overrides)


class IncludeStmtList(Node):
    """ node representing a list of include statements"""

    entries = pod.Field("a list of include statements", list,
                        initial_fn=list, assign_filter_list=[
                            pod.typed, pod.typed.sequence(Node), pod.const])

    @staticmethod
    def parse(
        text: str, lineno: int=1, col_offset: int=0
    ) -> "IncludeStmtList":
        """
        Parse a multi-line ``include`` field.

        This field is a simple list of :class:`IncludeStmt` with the added
        twist that empty lines (including lines containing just irrelevant
        white-space or comments) are silently ignored.


        Example:
            >>> IncludeStmtList.parse('''
            ...                       foo
            ...                       # comment
            ...                       bar''')
            ... # doctest: +NORMALIZE_WHITESPACE
            IncludeStmtList(entries=[IncludeStmt(pattern=ReFixed(text='foo'),
                                                 overrides=[]),
                                     IncludeStmt(pattern=ReFixed(text='bar'),
                                                 overrides=[])])
        """
        entries = []
        initial_lineno = lineno
        # NOTE: lineno is consciously shadowed below
        for lineno, line in enumerate(text.splitlines(), lineno):
            if WordScanner(line).get_token()[0] == WordScanner.TOKEN_EOF:
                # XXX: hack to work around the fact that each line is scanned
                # separately so there is no way to naturally progress to the
                # next line yet.
                continue
            entries.append(IncludeStmt.parse(line, lineno, col_offset))
        return IncludeStmtList(initial_lineno, col_offset, entries)


class WordList(Node):
    """ node representing a list of words"""

    entries = pod.Field("a list of words", list, initial_fn=list,
                        assign_filter_list=[pod.typed,
                                            pod.typed.sequence(Node),
                                            pod.const])

    @staticmethod
    def parse(
        text: str, lineno: int=1, col_offset: int=0
    ) -> "WordList":
        """
        Parse a list of words.

        Words are naturally separated by whitespace. Words can be quoted using
        double quotes. Words can be optionally separated with commas although
        those are discarded and entirely optional.

        Some basic examples:

            >>> WordList.parse("foo, bar")
            WordList(entries=[Text(text='foo'), Text(text='bar')])
            >>> WordList.parse("foo,bar")
            WordList(entries=[Text(text='foo'), Text(text='bar')])
            >>> WordList.parse("foo,,,,bar")
            WordList(entries=[Text(text='foo'), Text(text='bar')])
            >>> WordList.parse("foo,,,,bar,,")
            WordList(entries=[Text(text='foo'), Text(text='bar')])

        Words can be quoted, this allows us to include all kinds of characters
        inside:

            >>> WordList.parse('"foo bar"')
            WordList(entries=[Text(text='foo bar')])

        One word of caution, since we use one (and not a very smart one at
        that) scanner, the equals sign is recognized and rejected as incorrect
        input.

            >>> WordList.parse("=")
            WordList(entries=[Error(msg="Unexpected input: '='")])

        """
        entries = []
        scanner = WordScanner(text)
        while True:
            token, lexeme = scanner.get_token()
            if token == scanner.TOKEN_EOF:
                break
            elif token == scanner.TokenEnum.COMMA:
                continue
            elif token == scanner.TokenEnum.WORD:
                entries.append(Text(lineno, col_offset, lexeme))
            else:
                entries.append(
                    Error(lineno, col_offset,
                          "Unexpected input: {!r}".format(lexeme)))
        return WordList(lineno, col_offset, entries)
