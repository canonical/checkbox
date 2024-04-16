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
import operator

from plainbox.abc import IUnitQualifier
from plainbox.impl.job import JobDefinition
from plainbox.impl.secure.origin import FileTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.origin import UnknownTextSource
from plainbox.impl.secure.qualifiers import CompositeQualifier
from plainbox.impl.secure.qualifiers import FieldQualifier
from plainbox.impl.secure.qualifiers import IMatcher
from plainbox.impl.secure.qualifiers import JobIdQualifier
from plainbox.impl.secure.qualifiers import NonPrimitiveQualifierOrigin
from plainbox.impl.secure.qualifiers import OperatorMatcher
from plainbox.impl.secure.qualifiers import PatternMatcher
from plainbox.impl.secure.qualifiers import RegExpJobQualifier
from plainbox.impl.secure.qualifiers import select_units
from plainbox.impl.secure.qualifiers import SimpleQualifier
from plainbox.impl.testing_utils import make_job
from plainbox.vendor import mock


class IUnitQualifierTests(TestCase):
    """
    Test cases for IUnitQualifier interface
    """

    def test_IUnitQualifier_is_abstract(self):
        """
        Verify that IUnitQualifier is an interface and cannot be
        instantiated
        """
        self.assertRaises(TypeError, IUnitQualifier)


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
        self.origin = mock.Mock(name="origin", spec_set=Origin)
        self.obj = DummySimpleQualifier(self.origin)
        self.job = JobDefinition({"id": "dummy"})

    def test_init(self):
        """
        verify that SimpleQualifier has a working initializer that sets the
        inclusive flag
        """
        obj1 = DummySimpleQualifier(self.origin)
        self.assertEqual(obj1.origin, self.origin)
        self.assertEqual(obj1.inclusive, True)
        obj2 = DummySimpleQualifier(self.origin, False)
        self.assertEqual(obj2.origin, self.origin)
        self.assertEqual(obj2.inclusive, False)
        obj3 = DummySimpleQualifier(self.origin, inclusive=False)
        self.assertEqual(obj3.origin, self.origin)
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
        with mock.patch.object(self.obj, "get_vote") as mock_get_vote:
            mock_get_vote.return_value = IUnitQualifier.VOTE_INCLUDE
            self.assertTrue(self.obj.designates(self.job))
            mock_get_vote.return_value = IUnitQualifier.VOTE_EXCLUDE
            self.assertFalse(self.obj.designates(self.job))
            mock_get_vote.return_value = IUnitQualifier.VOTE_IGNORE
            self.assertFalse(self.obj.designates(self.job))

    def test_get_vote__inclusive_matching(self):
        """
        verify that SimpleQualifier.get_vote() returns VOTE_INCLUDE for
        inclusive qualifier that matches a job
        """
        obj = DummySimpleQualifier(self.origin, inclusive=True)
        with mock.patch.object(obj, "get_simple_match") as mock_gsm:
            mock_gsm.return_value = True
            self.assertEqual(
                obj.get_vote(self.job), IUnitQualifier.VOTE_INCLUDE
            )

    def test_get_vote__not_inclusive_matching(self):
        """
        verify that SimpleQualifier.get_vote() returns VOTE_EXCLUDE for
        non-inclusive qualifier that matches a job
        """
        obj = DummySimpleQualifier(self.origin, inclusive=False)
        with mock.patch.object(obj, "get_simple_match") as mock_gsm:
            mock_gsm.return_value = True
            self.assertEqual(
                obj.get_vote(self.job), IUnitQualifier.VOTE_EXCLUDE
            )

    def test_get_vote__inclusive_nonmatching(self):
        """
        verify that SimpleQualifier.get_vote() returns VOTE_IGNORE for
        inclusive qualifier that does not match a job
        """
        obj = DummySimpleQualifier(self.origin, inclusive=True)
        with mock.patch.object(obj, "get_simple_match") as mock_gsm:
            mock_gsm.return_value = False
            self.assertEqual(
                obj.get_vote(self.job), IUnitQualifier.VOTE_IGNORE
            )

    def test_get_vote__not_inclusive_nonmatching(self):
        """
        verify that SimpleQualifier.get_vote() returns VOTE_IGNORE for
        non-inclusive qualifier that does not match a job
        """
        obj = DummySimpleQualifier(self.origin, inclusive=False)
        with mock.patch.object(obj, "get_simple_match") as mock_gsm:
            mock_gsm.return_value = False
            self.assertEqual(
                obj.get_vote(self.job), IUnitQualifier.VOTE_IGNORE
            )

    def test_get_primitive_qualifiers(self):
        """
        verify that SimpleQualifier.get_primitive_qualifiers() returns a list
        with itself
        """
        return self.assertEqual(
            self.obj.get_primitive_qualifiers(), [self.obj]
        )


class OperatorMatcherTests(TestCase):
    """
    Test cases for OperatorMatcher class
    """

    def test_match(self):
        matcher = OperatorMatcher(operator.eq, "foo")
        self.assertTrue(matcher.match("foo"))
        self.assertFalse(matcher.match("bar"))

    def test_repr(self):
        self.assertEqual(
            repr(OperatorMatcher(operator.eq, "foo")),
            "OperatorMatcher(<built-in function eq>, 'foo')",
        )


class PatternMatcherTests(TestCase):
    """
    Test cases for PatternMatcher class
    """

    def test_match(self):
        matcher = PatternMatcher("foo.*")
        self.assertTrue(matcher.match("foobar"))
        self.assertFalse(matcher.match("fo"))

    def test_repr(self):
        self.assertEqual(
            repr(PatternMatcher("text")), "PatternMatcher('text')"
        )


class FieldQualifierTests(TestCase):
    """
    Test cases for FieldQualifier class
    """

    _FIELD = "field"

    def setUp(self):
        self.matcher = mock.Mock(name="matcher", spec_set=IMatcher)
        self.origin = mock.Mock(name="origin", spec_set=Origin)
        self.qualifier_i = FieldQualifier(
            self._FIELD, self.matcher, self.origin, True
        )
        self.qualifier_e = FieldQualifier(
            self._FIELD, self.matcher, self.origin, False
        )

    def test_init(self):
        """
        verify that FiledQualifier sets all of the properties correctly
        """
        self.assertEqual(self.qualifier_i.field, self._FIELD)
        self.assertEqual(self.qualifier_i.matcher, self.matcher)
        self.assertEqual(self.qualifier_i.origin, self.origin)
        self.assertEqual(self.qualifier_i.inclusive, True)

    def test_is_primitive(self):
        """
        verify that FieldQualifier.is_primitive is True
        """
        self.assertTrue(self.qualifier_i.is_primitive)
        self.assertTrue(self.qualifier_e.is_primitive)

    def test_repr(self):
        """
        verify that FieldQualifier.__repr__() works as expected
        """
        self.assertEqual(
            repr(self.qualifier_i),
            "FieldQualifier({!r}, {!r}, inclusive=True)".format(
                self._FIELD, self.matcher
            ),
        )
        self.assertEqual(
            repr(self.qualifier_e),
            "FieldQualifier({!r}, {!r}, inclusive=False)".format(
                self._FIELD, self.matcher
            ),
        )

    def test_get_simple_match(self):
        """
        verify that FieldQualifier.get_simple_match() works as expected
        """
        job = mock.Mock()
        for qualifier in (self.qualifier_i, self.qualifier_e):
            self.matcher.reset_mock()
            result = qualifier.get_simple_match(job)
            self.matcher.match.assert_called_once_with(
                getattr(job, self._FIELD)
            )
            self.assertEqual(result, self.matcher.match())

    def test_field_setter(self):
        self.assertEqual(self.qualifier_e.field, self._FIELD)
        self.qualifier_e.field = "updated"
        self.assertEqual(self.qualifier_e.field, "updated")


class RegExpJobQualifierTests(TestCase):
    """
    Test cases for RegExpJobQualifier class
    """

    def setUp(self):
        self.origin = mock.Mock(name="origin", spec_set=Origin)
        self.qualifier = RegExpJobQualifier("f.*", self.origin)

    def test_init(self):
        """
        verify that init assigns stuff to properties correctly
        """
        self.assertEqual(self.qualifier.pattern_text, "f.*")
        self.assertEqual(self.qualifier.origin, self.origin)

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
            repr(self.qualifier), "RegExpJobQualifier('f.*', inclusive=True)"
        )

    def test_get_vote(self):
        """
        verify that RegExpJobQualifier.get_vote() works as expected
        """
        self.assertEqual(
            RegExpJobQualifier("foo", self.origin).get_vote(
                JobDefinition({"id": "foo"})
            ),
            IUnitQualifier.VOTE_INCLUDE,
        )
        self.assertEqual(
            RegExpJobQualifier("foo", self.origin, inclusive=False).get_vote(
                JobDefinition({"id": "foo"})
            ),
            IUnitQualifier.VOTE_EXCLUDE,
        )
        self.assertEqual(
            RegExpJobQualifier("foo", self.origin).get_vote(
                JobDefinition({"id": "bar"})
            ),
            IUnitQualifier.VOTE_IGNORE,
        )
        self.assertEqual(
            RegExpJobQualifier("foo", self.origin, inclusive=False).get_vote(
                JobDefinition({"id": "bar"})
            ),
            IUnitQualifier.VOTE_IGNORE,
        )


class JobIdQualifierTests(TestCase):
    """
    Test cases for JobIdQualifier class
    """

    def setUp(self):
        self.origin = mock.Mock(name="origin", spec_set=Origin)
        self.qualifier = JobIdQualifier("foo", self.origin)

    def test_init(self):
        """
        verify that init assigns stuff to properties correctly
        """
        self.assertEqual(self.qualifier.id, "foo")
        self.assertEqual(self.qualifier.origin, self.origin)

    def test_is_primitive(self):
        """
        verify that JobIdQualifier.is_primitive is True
        """
        self.assertTrue(self.qualifier.is_primitive)

    def test_repr(self):
        """
        verify that JobIdQualifier.__repr__() works as expected
        """
        self.assertEqual(
            repr(self.qualifier), "JobIdQualifier('foo', inclusive=True)"
        )

    def test_get_vote(self):
        """
        verify that JobIdQualifier.get_vote() works as expected
        """
        self.assertEqual(
            JobIdQualifier("foo", self.origin).get_vote(
                JobDefinition({"id": "foo"})
            ),
            IUnitQualifier.VOTE_INCLUDE,
        )
        self.assertEqual(
            JobIdQualifier("foo", self.origin, inclusive=False).get_vote(
                JobDefinition({"id": "foo"})
            ),
            IUnitQualifier.VOTE_EXCLUDE,
        )
        self.assertEqual(
            JobIdQualifier("foo", self.origin).get_vote(
                JobDefinition({"id": "bar"})
            ),
            IUnitQualifier.VOTE_IGNORE,
        )
        self.assertEqual(
            JobIdQualifier("foo", self.origin, inclusive=False).get_vote(
                JobDefinition({"id": "bar"})
            ),
            IUnitQualifier.VOTE_IGNORE,
        )

    def test_smoke(self):
        """
        various smoke tests that check if JobIdQualifier.designates() works
        """
        self.assertTrue(
            JobIdQualifier("name", self.origin).designates(make_job("name"))
        )
        self.assertFalse(
            JobIdQualifier("nam", self.origin).designates(make_job("name"))
        )
        self.assertFalse(
            JobIdQualifier(".*", self.origin).designates(make_job("name"))
        )
        self.assertFalse(
            JobIdQualifier("*", self.origin).designates(make_job("name"))
        )


class CompositeQualifierTests(TestCase):
    """
    Test cases for CompositeQualifier class
    """

    def setUp(self):
        self.origin = mock.Mock(name="origin", spec_set=Origin)

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
            IUnitQualifier.VOTE_IGNORE,
        )
        # Any match is INCLUDE
        self.assertEqual(
            CompositeQualifier(
                [
                    RegExpJobQualifier("foo", self.origin),
                ]
            ).get_vote(make_job("foo")),
            IUnitQualifier.VOTE_INCLUDE,
        )
        # Any negative match is EXCLUDE
        self.assertEqual(
            CompositeQualifier(
                [
                    RegExpJobQualifier("foo", self.origin, inclusive=False),
                ]
            ).get_vote(make_job("foo")),
            IUnitQualifier.VOTE_EXCLUDE,
        )
        # Negative matches take precedence over positive matches
        self.assertEqual(
            CompositeQualifier(
                [
                    RegExpJobQualifier("foo", self.origin),
                    RegExpJobQualifier("foo", self.origin, inclusive=False),
                ]
            ).get_vote(make_job("foo")),
            IUnitQualifier.VOTE_EXCLUDE,
        )
        # Unrelated patterns are not affecting the result
        self.assertEqual(
            CompositeQualifier(
                [
                    RegExpJobQualifier("foo", self.origin),
                    RegExpJobQualifier("bar", self.origin),
                ]
            ).get_vote(make_job("foo")),
            IUnitQualifier.VOTE_INCLUDE,
        )

    def test_inclusive(self):
        """
        verify that inclusive selection works
        """
        self.assertTrue(
            CompositeQualifier(
                [
                    RegExpJobQualifier("foo", self.origin),
                ]
            ).designates(make_job("foo"))
        )
        self.assertFalse(
            CompositeQualifier(
                [
                    RegExpJobQualifier("foo", self.origin),
                ]
            ).designates(make_job("bar"))
        )

    def test_exclusive(self):
        """
        verify that non-inclusive selection works
        """
        self.assertFalse(
            CompositeQualifier(
                [RegExpJobQualifier("foo", self.origin, inclusive=False)]
            ).designates(make_job("foo"))
        )
        self.assertFalse(
            CompositeQualifier(
                [
                    RegExpJobQualifier(".*", self.origin),
                    RegExpJobQualifier("foo", self.origin, inclusive=False),
                ]
            ).designates(make_job("foo"))
        )
        self.assertTrue(
            CompositeQualifier(
                [
                    RegExpJobQualifier(".*", self.origin),
                    RegExpJobQualifier("foo", self.origin, inclusive=False),
                ]
            ).designates(make_job("bar"))
        )

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
        q1 = JobIdQualifier("q1", self.origin)
        q2 = JobIdQualifier("q2", self.origin)
        q3 = JobIdQualifier("q3", self.origin)
        # we expect to see them flattened
        expected = [q1, q2, q3]
        # from a nested structure like this
        measured = CompositeQualifier(
            [CompositeQualifier([q1, q2]), q3]
        ).get_primitive_qualifiers()
        self.assertEqual(expected, measured)

    def test_origin(self):
        with self.assertRaises(NonPrimitiveQualifierOrigin):
            CompositeQualifier([]).origin


class FunctionTests(TestCase):

    def setUp(self):
        self.origin = mock.Mock(name="origin", spec_set=Origin)

    def test_select_units__empty_qualifier_list(self):
        """
        verify that select_units() returns an empty list if no qualifiers are
        passed
        """
        self.assertEqual(select_units([], []), [])

    def test_select_units__inclusion(self):
        """
        verify that select_units() honors qualifier ordering
        """
        job_a = JobDefinition({"id": "a"})
        job_b = JobDefinition({"id": "b"})
        job_c = JobDefinition({"id": "c"})
        qual_a = JobIdQualifier("a", self.origin)
        qual_c = JobIdQualifier("c", self.origin)
        for job_list in permutations([job_a, job_b, job_c], 3):
            # Regardless of how the list of job is ordered the result
            # should be the same, depending on the qualifier list
            self.assertEqual(
                select_units(job_list, [qual_a, qual_c]), [job_a, job_c]
            )

    def test_select_units__exclusion(self):
        """
        verify that select_units() honors qualifier ordering
        """
        job_a = JobDefinition({"id": "a"})
        job_b = JobDefinition({"id": "b"})
        job_c = JobDefinition({"id": "c"})
        qual_all = CompositeQualifier(
            [
                JobIdQualifier("a", self.origin),
                JobIdQualifier("b", self.origin),
                JobIdQualifier("c", self.origin),
            ]
        )
        qual_not_c = JobIdQualifier("c", self.origin, inclusive=False)
        for job_list in permutations([job_a, job_b, job_c], 3):
            # Regardless of how the list of job is ordered the result
            # should be the same, depending on the qualifier list
            self.assertEqual(
                select_units(job_list, [qual_all, qual_not_c]), [job_a, job_b]
            )

    def test_select_units__id_field_qualifier(self):
        """
        verify that select_units() only returns the job that matches a given
        FieldQualifier
        """
        job_a = JobDefinition({"id": "a"})
        job_b = JobDefinition({"id": "b"})
        job_c = JobDefinition({"id": "c"})
        matcher = OperatorMatcher(operator.eq, "a")
        qual = FieldQualifier("id", matcher, self.origin, True)
        job_list = [job_a, job_b, job_c]
        expected_list = [job_a]
        self.assertEqual(select_units(job_list, [qual]), expected_list)

    def test_select_units__id_field_qualifier_twice(self):
        """
        verify that select_units() only returns the job that matches a given
        FieldQualifier once, even if it has been added twice
        """
        job_a = JobDefinition({"id": "a"})
        matcher = OperatorMatcher(operator.eq, "a")
        qual = FieldQualifier("id", matcher, self.origin, True)
        job_list = [job_a, job_a]
        expected_list = [job_a]
        self.assertEqual(select_units(job_list, [qual, qual]), expected_list)

    def test_select_units__template_id_field_qualifier(self):
        """
        verify that select_units() only returns the jobs that have been
        instantiated using a given template
        """
        job_a = JobDefinition(
            {
                "id": "a",
            }
        )
        templated_job_b = JobDefinition(
            {
                "id": "b",
                "template-id": "test-template",
            }
        )
        templated_job_c = JobDefinition(
            {
                "id": "c",
                "template-id": "test-template",
            }
        )
        matcher = OperatorMatcher(operator.eq, "test-template")
        qual = FieldQualifier("id", matcher, self.origin, True)
        job_list = [job_a, templated_job_b, templated_job_c]
        expected_list = [templated_job_b, templated_job_c]
        self.assertEqual(select_units(job_list, [qual]), expected_list)

    def test_select_units__excluded_templated_job(self):
        """
        verify that if a template id is included in the test plan, jobs that
        have been instantiated from it can still be excluded from the list of
        selected jobs
        """
        templated_job_a = JobDefinition(
            {
                "id": "a",
                "template-id": "test-template",
            }
        )
        templated_job_b = JobDefinition(
            {
                "id": "b",
                "template-id": "test-template",
            }
        )
        matcher_incl = OperatorMatcher(operator.eq, "test-template")
        matcher_excl = OperatorMatcher(operator.eq, "b")
        qual_incl = FieldQualifier("id", matcher_incl, self.origin, True)
        qual_excl = FieldQualifier("id", matcher_excl, self.origin, False)
        job_list = [templated_job_a, templated_job_b]
        qualifiers = [qual_incl, qual_excl]
        expected_list = [templated_job_a]
        self.assertEqual(select_units(job_list, qualifiers), expected_list)
