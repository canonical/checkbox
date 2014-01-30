# This file is part of Checkbox.
#
# Copyright 2013, 2014 Canonical Ltd.
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
plainbox.impl.secure.test_qualifiers
====================================

Test definitions for plainbox.impl.secure.qualifiers module
"""

from contextlib import contextmanager
from io import TextIOWrapper
from itertools import permutations
from unittest import TestCase

from plainbox.abc import IJobQualifier
from plainbox.impl.job import JobDefinition
from plainbox.impl.secure.qualifiers import CompositeQualifier
from plainbox.impl.secure.qualifiers import NameJobQualifier
from plainbox.impl.secure.qualifiers import RegExpJobQualifier
from plainbox.impl.secure.qualifiers import SimpleQualifier
from plainbox.impl.secure.qualifiers import WhiteList
from plainbox.impl.secure.qualifiers import select_jobs
from plainbox.impl.secure.rfc822 import FileTextSource
from plainbox.impl.secure.rfc822 import Origin
from plainbox.impl.secure.rfc822 import UnknownTextSource
from plainbox.impl.testing_utils import make_job
from plainbox.vendor import mock


class IJobQualifierTests(TestCase):
    """
    Test cases for IJobQualifier interface
    """

    def test_IJobQualifier_is_abstract(self):
        """
        Verify that IJobQualifier is an interface and cannot be
        instantiated
        """
        self.assertRaises(TypeError, IJobQualifier)


class DummySimpleQualifier(SimpleQualifier):
    """
    Dummy concrete subclass of SimpleQualifier
    """

    def get_simple_match(self, job):
        raise NotImplementedError()  # pragma: no cover


class SimpleQualifierTests(TestCase):
    """
    Test cases for SimpleQualifier class
    """

    def setUp(self):
        self.obj = DummySimpleQualifier()
        self.job = JobDefinition({'name': "dummy"})

    def test_init(self):
        """
        verify that SimpleQualifier has a working initializer that sets the
        inclusive flag
        """
        obj1 = DummySimpleQualifier()
        self.assertEqual(obj1.inclusive, True)
        obj2 = DummySimpleQualifier(False)
        self.assertEqual(obj2.inclusive, False)
        obj3 = DummySimpleQualifier(inclusive=False)
        self.assertEqual(obj3.inclusive, False)

    def test_is_primitive(self):
        """
        verify that SimpleQualifier.is_primitive is True
        """
        self.assertTrue(self.obj.is_primitive)

    def test_designates(self):
        """
        verify that SimpleQualifier.designates returns True iff get_vote() for
        the same job returns VOTE_INCLUDE.
        """
        with mock.patch.object(self.obj, 'get_vote') as mock_get_vote:
            mock_get_vote.return_value = IJobQualifier.VOTE_INCLUDE
            self.assertTrue(self.obj.designates(self.job))
            mock_get_vote.return_value = IJobQualifier.VOTE_EXCLUDE
            self.assertFalse(self.obj.designates(self.job))
            mock_get_vote.return_value = IJobQualifier.VOTE_IGNORE
            self.assertFalse(self.obj.designates(self.job))

    def test_get_vote__inclusive_matching(self):
        """
        verify that SimpleQualifier.get_vote() returns VOTE_INCLUDE for
        inclusive qualifier that matches a job
        """
        obj = DummySimpleQualifier(inclusive=True)
        with mock.patch.object(obj, 'get_simple_match') as mock_gsm:
            mock_gsm.return_value = True
            self.assertEqual(obj.get_vote(self.job),
                             IJobQualifier.VOTE_INCLUDE)

    def test_get_vote__not_inclusive_matching(self):
        """
        verify that SimpleQualifier.get_vote() returns VOTE_EXCLUDE for
        non-inclusive qualifier that matches a job
        """
        obj = DummySimpleQualifier(inclusive=False)
        with mock.patch.object(obj, 'get_simple_match') as mock_gsm:
            mock_gsm.return_value = True
            self.assertEqual(obj.get_vote(self.job),
                             IJobQualifier.VOTE_EXCLUDE)

    def test_get_vote__inclusive_nonmatching(self):
        """
        verify that SimpleQualifier.get_vote() returns VOTE_IGNORE for
        inclusive qualifier that does not match a job
        """
        obj = DummySimpleQualifier(inclusive=True)
        with mock.patch.object(obj, 'get_simple_match') as mock_gsm:
            mock_gsm.return_value = False
            self.assertEqual(obj.get_vote(self.job), IJobQualifier.VOTE_IGNORE)

    def test_get_vote__not_inclusive_nonmatching(self):
        """
        verify that SimpleQualifier.get_vote() returns VOTE_IGNORE for
        non-inclusive qualifier that does not match a job
        """
        obj = DummySimpleQualifier(inclusive=False)
        with mock.patch.object(obj, 'get_simple_match') as mock_gsm:
            mock_gsm.return_value = False
            self.assertEqual(obj.get_vote(self.job), IJobQualifier.VOTE_IGNORE)

    def test_get_primitive_qualifiers(self):
        """
        verify that SimpleQualifier.get_primitive_qualifiers() returns a list
        with itself
        """
        return self.assertEqual(
            self.obj.get_primitive_qualifiers(), [self.obj])


class RegExpJobQualifierTests(TestCase):
    """
    Test cases for RegExpJobQualifier class
    """

    def setUp(self):
        self.qualifier = RegExpJobQualifier("f.*")

    def test_is_primitive(self):
        """
        verify that RegExpJobQualifier.is_primitive is True
        """
        self.assertTrue(self.qualifier.is_primitive)

    def test_pattern_text(self):
        """
        verify that RegExpJobQualifier.pattern_text returns
        the full text of the pattern
        """
        self.assertEqual(self.qualifier.pattern_text, "f.*")

    def test_repr(self):
        """
        verify that RegExpJobQualifier.__repr__() works as expected
        """
        self.assertEqual(
            repr(self.qualifier), "RegExpJobQualifier('f.*', inclusive=True)")

    def test_get_vote(self):
        """
        verify that RegExpJobQualifier.get_vote() works as expected
        """
        self.assertEqual(
            RegExpJobQualifier("foo").get_vote(
                JobDefinition({'name': 'foo'})),
            IJobQualifier.VOTE_INCLUDE)
        self.assertEqual(
            RegExpJobQualifier("foo", inclusive=False).get_vote(
                JobDefinition({'name': 'foo'})),
            IJobQualifier.VOTE_EXCLUDE)
        self.assertEqual(
            RegExpJobQualifier("foo").get_vote(
                JobDefinition({'name': 'bar'})),
            IJobQualifier.VOTE_IGNORE)
        self.assertEqual(
            RegExpJobQualifier("foo", inclusive=False).get_vote(
                JobDefinition({'name': 'bar'})),
            IJobQualifier.VOTE_IGNORE)


class NameJobQualifierTests(TestCase):
    """
    Test cases for NameJobQualifier class
    """

    def setUp(self):
        self.qualifier = NameJobQualifier("foo")

    def test_is_primitive(self):
        """
        verify that NameJobQualifier.is_primitive is True
        """
        self.assertTrue(self.qualifier.is_primitive)

    def test_repr(self):
        """
        verify that NameJobQualifier.__repr__() works as expected
        """
        self.assertEqual(
            repr(self.qualifier), "NameJobQualifier('foo', inclusive=True)")

    def test_get_vote(self):
        """
        verify that NameJobQualifier.get_vote() works as expected
        """
        self.assertEqual(
            NameJobQualifier("foo").get_vote(
                JobDefinition({'name': 'foo'})),
            IJobQualifier.VOTE_INCLUDE)
        self.assertEqual(
            NameJobQualifier("foo", inclusive=False).get_vote(
                JobDefinition({'name': 'foo'})),
            IJobQualifier.VOTE_EXCLUDE)
        self.assertEqual(
            NameJobQualifier("foo").get_vote(
                JobDefinition({'name': 'bar'})),
            IJobQualifier.VOTE_IGNORE)
        self.assertEqual(
            NameJobQualifier("foo", inclusive=False).get_vote(
                JobDefinition({'name': 'bar'})),
            IJobQualifier.VOTE_IGNORE)

    def test_smoke(self):
        """
        various smoke tests that check if NameJobQualifier.designates() works
        """
        self.assertTrue(NameJobQualifier('name').designates(make_job('name')))
        self.assertFalse(NameJobQualifier('nam').designates(make_job('name')))
        self.assertFalse(NameJobQualifier('.*').designates(make_job('name')))
        self.assertFalse(NameJobQualifier('*').designates(make_job('name')))


class CompositeQualifierTests(TestCase):
    """
    Test cases for CompositeQualifier class
    """

    def test_empty(self):
        """
        verify that an empty CompositeQualifier does not designate a random job
        """
        obj = CompositeQualifier([])
        self.assertFalse(obj.designates(make_job("foo")))

    def test_get_vote(self):
        """
        verify how CompositeQualifier.get_vote() behaves in various situations
        """
        # Default is IGNORE
        self.assertEqual(
            CompositeQualifier([]).get_vote(make_job("foo")),
            IJobQualifier.VOTE_IGNORE)
        # Any match is INCLUDE
        self.assertEqual(
            CompositeQualifier([
                RegExpJobQualifier("foo"),
            ]).get_vote(make_job("foo")),
            IJobQualifier.VOTE_INCLUDE)
        # Any negative match is EXCLUDE
        self.assertEqual(
            CompositeQualifier([
                RegExpJobQualifier("foo", inclusive=False),
            ]).get_vote(make_job("foo")),
            IJobQualifier.VOTE_EXCLUDE)
        # Negative matches take precedence over positive matches
        self.assertEqual(
            CompositeQualifier([
                RegExpJobQualifier("foo"),
                RegExpJobQualifier("foo", inclusive=False),
            ]).get_vote(make_job("foo")),
            IJobQualifier.VOTE_EXCLUDE)
        # Unrelated patterns are not affecting the result
        self.assertEqual(
            CompositeQualifier([
                RegExpJobQualifier("foo"),
                RegExpJobQualifier("bar"),
            ]).get_vote(make_job("foo")),
            IJobQualifier.VOTE_INCLUDE)

    def test_inclusive(self):
        """
        verify that inclusive selection works
        """
        self.assertTrue(
            CompositeQualifier([
                RegExpJobQualifier('foo'),
            ]).designates(make_job("foo")))
        self.assertFalse(
            CompositeQualifier([
                RegExpJobQualifier('foo'),
            ]).designates(make_job("bar")))

    def test_exclusive(self):
        """
        verify that non-inclusive selection works
        """
        self.assertFalse(
            CompositeQualifier([
                RegExpJobQualifier('foo', inclusive=False)
            ]).designates(make_job("foo")))
        self.assertFalse(
            CompositeQualifier([
                RegExpJobQualifier(".*"),
                RegExpJobQualifier('foo', inclusive=False)
            ]).designates(make_job("foo")))
        self.assertTrue(
            CompositeQualifier([
                RegExpJobQualifier(".*"),
                RegExpJobQualifier('foo', inclusive=False)
            ]).designates(make_job("bar")))

    def test_is_primitive(self):
        """
        verify that CompositeQualifier.is_primitive is False
        """
        self.assertFalse(CompositeQualifier([]).is_primitive)

    def test_get_primitive_qualifiers(self):
        """
        verify that CompositeQualifiers.get_composite_qualifiers() works
        """
        # given three qualifiers
        q1 = NameJobQualifier("q1")
        q2 = NameJobQualifier("q2")
        q3 = NameJobQualifier("q3")
        # we expect to see them flattened
        expected = [q1, q2, q3]
        # from a nested structure like this
        measured = CompositeQualifier([
            CompositeQualifier([q1, q2]), q3]
        ).get_primitive_qualifiers()
        self.assertEqual(expected, measured)


class WhiteListTests(TestCase):
    """
    Test cases for WhiteList class
    """

    _name = 'whitelist.txt'

    _content = [
        "# this is a comment",
        "foo # this is another comment",
        "bar",
        ""
    ]

    @contextmanager
    def mocked_file(self, name, content):
        m_open = mock.MagicMock(name='open', spec=open)
        m_stream = mock.MagicMock(spec=TextIOWrapper)
        m_stream.__enter__.return_value = m_stream
        # The next two lines are complementary, either will suffice but the
        # test may need changes if the code that reads stuff changes.
        m_stream.__iter__.side_effect = lambda: iter(content)
        m_stream.read.return_value = "\n".join(content)
        m_open.return_value = m_stream
        with mock.patch('plainbox.impl.secure.qualifiers.open', m_open,
                        create=True):
            yield
        m_open.assert_called_once_with(name, "rt", encoding="UTF-8")

    def test_load_patterns(self):
        with self.mocked_file(self._name, self._content):
            pattern_list, max_lineno = WhiteList._load_patterns(self._name)
        self.assertEqual(pattern_list, ['^foo$', '^bar$'])
        self.assertEqual(max_lineno, 3)

    def test_designates(self):
        """
        verify that WhiteList.designates() works
        """
        self.assertTrue(
            WhiteList.from_string("foo").designates(make_job('foo')))
        self.assertTrue(
            WhiteList.from_string("foo\nbar\n").designates(make_job('foo')))
        self.assertTrue(
            WhiteList.from_string("foo\nbar\n").designates(make_job('bar')))
        # Note, it's not matching either!
        self.assertFalse(
            WhiteList.from_string("foo").designates(make_job('foobar')))
        self.assertFalse(
            WhiteList.from_string("bar").designates(make_job('foobar')))

    def test_from_file(self):
        """
        verify that WhiteList.from_file() works
        """
        with self.mocked_file(self._name, self._content):
            whitelist = WhiteList.from_file(self._name)
        # verify that the patterns are okay
        self.assertEqual(
            repr(whitelist.qualifier_list[0]),
            "RegExpJobQualifier('^foo$', inclusive=True)")
        # verify that whitelist name got set
        self.assertEqual(whitelist.name, "whitelist")
        # verify that the origin got set
        self.assertEqual(
            whitelist.origin,
            Origin(FileTextSource("whitelist.txt"), 1, 3))

    def test_from_string(self):
        """
        verify that WhiteList.from_string() works
        """
        whitelist = WhiteList.from_string("\n".join(self._content))
        # verify that the patterns are okay
        self.assertEqual(
            repr(whitelist.qualifier_list[0]),
            "RegExpJobQualifier('^foo$', inclusive=True)")
        # verify that whitelist name is the empty default
        self.assertEqual(whitelist.name, None)
        # verify that the origin got set to the default constructed value
        self.assertEqual(whitelist.origin, Origin(UnknownTextSource(), 1, 3))

    def test_from_empty_string(self):
        """
        verify that WhiteList.from_string("") works
        """
        WhiteList.from_string("")

    def test_from_string__with_name_and_origin(self):
        """
        verify that WhiteList.from_string() works when passing name and origin
        """
        # construct a whitelist with some dummy data, the names, pathnames and
        # line ranges are arbitrary
        whitelist = WhiteList.from_string(
            "\n".join(self._content), name="somefile",
            origin=Origin(FileTextSource("somefile.txt"), 1, 3))
        # verify that the patterns are okay
        self.assertEqual(
            repr(whitelist.qualifier_list[0]),
            "RegExpJobQualifier('^foo$', inclusive=True)")
        # verify that whitelist name is copied
        self.assertEqual(whitelist.name, "somefile")
        # verify that the origin is copied
        self.assertEqual(
            whitelist.origin, Origin(FileTextSource("somefile.txt"), 1, 3))

    def test_from_string__with_filename(self):
        """
        verify that WhiteList.from_string() works when passing filename
        """
        # construct a whitelist with some dummy data, the names, pathnames and
        # line ranges are arbitrary
        whitelist = WhiteList.from_string(
            "\n".join(self._content), filename="somefile.txt")
        # verify that the patterns are okay
        self.assertEqual(
            repr(whitelist.qualifier_list[0]),
            "RegExpJobQualifier('^foo$', inclusive=True)")
        # verify that whitelist name is derived from the filename
        self.assertEqual(whitelist.name, "somefile")
        # verify that the origin is properly derived from the filename
        self.assertEqual(
            whitelist.origin, Origin(FileTextSource("somefile.txt"), 1, 3))

    def test_repr(self):
        """
        verify that custom repr works
        """
        whitelist = WhiteList([], name="test")
        self.assertEqual(repr(whitelist), "<WhiteList name:'test'>")

    def test_name_getter(self):
        """
        verify that WhiteList.name getter works
        """
        self.assertEqual(WhiteList([], "foo").name, "foo")

    def test_name_setter(self):
        """
        verify that WhiteList.name setter works
        """
        whitelist = WhiteList([], "foo")
        whitelist.name = "bar"
        self.assertEqual(whitelist.name, "bar")

    def test_name_from_fielename(self):
        """
        verify how name_from_filename() works
        """
        self.assertEqual(
            WhiteList.name_from_filename("some/path/foo.whitelist"), "foo")
        self.assertEqual(WhiteList.name_from_filename("foo.whitelist"), "foo")
        self.assertEqual(WhiteList.name_from_filename("foo."), "foo")
        self.assertEqual(WhiteList.name_from_filename("foo"), "foo")
        self.assertEqual(
            WhiteList.name_from_filename("foo.notawhitelist"), "foo")


class FunctionTests(TestCase):

    def test_select_jobs__inclusion(self):
        """
        verify that select_jobs() honors qualifier ordering
        """
        job_a = JobDefinition({'name': 'a'})
        job_b = JobDefinition({'name': 'b'})
        job_c = JobDefinition({'name': 'c'})
        qual_a = NameJobQualifier("a")
        qual_c = NameJobQualifier("c")
        for job_list in permutations([job_a, job_b, job_c], 3):
            # Regardless of how the list of job is ordered the result
            # should be the same, depending on the qualifier list
            self.assertEqual(
                select_jobs(job_list, [qual_a, qual_c]),
                [job_a, job_c])

    def test_select_jobs__exclusion(self):
        """
        verify that select_jobs() honors qualifier ordering
        """
        job_a = JobDefinition({'name': 'a'})
        job_b = JobDefinition({'name': 'b'})
        job_c = JobDefinition({'name': 'c'})
        qual_all = CompositeQualifier([
            NameJobQualifier("a"),
            NameJobQualifier("b"),
            NameJobQualifier("c"),
        ])
        qual_not_c = NameJobQualifier("c", inclusive=False)
        for job_list in permutations([job_a, job_b, job_c], 3):
            # Regardless of how the list of job is ordered the result
            # should be the same, depending on the qualifier list
            self.assertEqual(
                select_jobs(job_list, [qual_all, qual_not_c]),
                [job_a, job_b])
