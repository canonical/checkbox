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
from doctest import DocTestSuite
from unittest import TestCase

from plainbox.impl.pod import Field
from plainbox.impl.pod import MANDATORY
from plainbox.impl.pod import POD
from plainbox.impl.pod import UNSET
from plainbox.impl.pod import _FieldCollection
from plainbox.vendor import mock


def load_tests(loader, tests, ignore):
    tests.addTests(DocTestSuite('plainbox.impl.pod'))
    return tests


class SingletonTests(TestCase):

    def test_MANDATORY_repr(self):
        self.assertEqual(repr(MANDATORY), "MANDATORY")

    def test_UNSET_repr(self):
        self.assertEqual(repr(UNSET), "UNSET")


class FieldTests(TestCase):

    FIELD_CLS = Field

    def setUp(self):
        self.doc = "doc"  # not a mock because it gets set to __doc__
        self.type = mock.Mock(name='type')
        self.initial = mock.Mock(name='initial')
        self.initial_fn = mock.Mock(name='initial_fn')
        self.field = self.FIELD_CLS(
            self.doc, self.type, self.initial, self.initial_fn)
        self.instance = mock.Mock(name='instance')
        self.owner = mock.Mock(name='owner')

    def test_initializer(self):
        """
        Field initializer properly stored all attributes
        """
        self.assertEqual(self.field.__doc__, self.doc)
        self.assertEqual(self.field.type, self.type)
        self.assertEqual(self.field.initial, self.initial)
        self.assertEqual(self.field.initial_fn, self.initial_fn)

    def test_gain_name(self):
        """
        Using gain_name() sets three extra attributes
        """
        self.assertIsNone(self.field.name)
        self.assertIsNone(self.field.instance_attr)
        self.assertIsNone(self.field.signal_name)
        self.field.gain_name("abcd")
        self.assertEqual(self.field.name, "abcd")
        self.assertEqual(self.field.instance_attr, "_abcd")
        self.assertEqual(self.field.signal_name, "on_abcd_changed")

    def test_repr(self):
        """
        Field has a working repr() method
        """
        self.field.gain_name("field")
        self.assertEqual(repr(self.field), "<Field name:'field'>")

    def test_is_mandatory(self):
        """
        Fields with the initial value of MANDATORY are mandatory
        """
        self.field.initial = None
        self.assertFalse(self.field.is_mandatory)
        self.field.initial = MANDATORY
        self.assertTrue(self.field.is_mandatory)

    def test_cls_reads(self):
        """
        Accessing fields on via the class exposes the field object itself
        """
        self.assertIs(self.field.__get__(None, self.owner), self.field)

    def test_obj_reads(self):
        """
        Accessing fields via an object reads data from the object
        """
        # Reading the field requires the field to know its name
        self.field.gain_name("field")
        self.assertEqual(
            self.field.__get__(self.instance, self.owner),
            self.instance._field)

    def test_obj_writes(self):
        """
        Writing fields via an object writes data to the object
        """
        # Writing the field requires the field to know its name
        self.field.gain_name("field")
        self.field.__set__(self.instance, "data")
        self.assertEqual(self.instance._field, "data")

    def test_obj_writes_fires_notification(self):
        """
        Writing fields via an object triggers notification, if enabled
        """
        # Let's enable notification and set the name so that the field knows
        # what to do when it gets set. Let's set the instance data to "old" to
        # track the actual change.
        self.field.notify = True
        self.field.gain_name("field")
        self.instance._field = "old"
        # Let's set the data to "new" now
        self.field.__set__(self.instance, "new")
        # And check that the notification system worked
        self.instance.on_field_changed.assert_called_with("old", "new")

    def test_obj_writes_uses_assign_chain(self):
        """
        Writing fields via an object uses the assign filter list
        """
        # Let's enable the assign filter composed out of two functions
        # and set some data using the field.
        fn1 = mock.Mock()
        fn2 = mock.Mock()
        self.field.assign_filter_list = [fn1, fn2]
        self.field.gain_name("field")
        self.instance._field = "old"
        self.field.__set__(self.instance, "new")
        # The current value in the field should be the return value of fn2()
        # and both fn1() and fn2() were called with the right arguments.
        fn1.assert_called_with(self.instance, self.field, "old", "new")
        fn2.assert_called_with(self.instance, self.field, "old", fn1())
        self.assertEqual(self.instance._field, fn2())

    def test_alter_cls_without_notification(self):
        """
        Using alter_cls() when notification is disabled does nothing
        """
        cls = mock.Mock(name='cls')
        del cls.on_field_changed
        self.field.notify = False
        self.field.gain_name('field')
        self.field.alter_cls(cls)
        self.assertFalse(hasattr(cls, "on_field_changed"))

    def test_alter_cls_with_notification(self):
        """
        Using alter_cls() when notification is enabled creates a signal
        """
        cls = mock.Mock(name='cls')
        del cls.on_field_changed
        cls.__name__ = "Klass"
        self.field.notify = True
        self.field.gain_name('field')
        self.field.alter_cls(cls)
        self.assertTrue(hasattr(cls, "on_field_changed"))
        self.assertEqual(
            cls.on_field_changed.signal_name, "Klass.on_field_changed")


class FieldCollectionTests(TestCase):

    def setUp(self):
        self.foo = Field()
        self.bar = Field()
        self.ns = {
            'foo': self.foo,
            'bar': self.bar,
            'do_sth': lambda: True,
            'DATA': 42,
        }
        self.fc = _FieldCollection()

    def set_field_names(self):
        self.foo.gain_name('foo')
        self.bar.gain_name('bar')

    def test_add_field_builds_field_list(self):
        """
        .add_field() appends new fields to field_list
        """
        # because we're not calling inspect_namespace() which does that
        self.set_field_names()
        self.fc.add_field(self.foo, 'cls')
        self.assertEqual(self.fc.field_list, [self.foo])
        self.fc.add_field(self.bar, 'cls')
        self.assertEqual(self.fc.field_list, [self.foo, self.bar])

    def test_add_field_builds_field_origin_map(self):
        """
        .add_field() builds and maintains field_origin_map
        """
        # because we're not calling inspect_namespace() which does that
        self.set_field_names()
        self.fc.add_field(self.foo, 'cls')
        self.assertEqual(self.fc.field_origin_map, {'foo': 'cls'})
        self.fc.add_field(self.bar, 'cls')
        self.assertEqual(
            self.fc.field_origin_map, {'foo': 'cls', 'bar': 'cls'})

    def test_add_field_detects_clashes(self):
        """
        .add_Field() detects field clashes and raises TypeError
        """
        foo_clash = Field()
        foo_clash.name = 'foo'
        # because we're not calling inspect_namespace() which does that
        self.set_field_names()
        self.fc.add_field(self.foo, 'cls')
        with self.assertRaisesRegex(
                TypeError, 'field other_cls.foo clashes with cls.foo'):
            self.fc.add_field(foo_clash, 'other_cls')

    def test_inspect_base_classes_calls_add_field(self):
        """
        .inspect_base_classes() calls add_field() on each Field found
        """

        class Base1(POD):
            foo = Field()
            bar = Field()

        class Base2(POD):
            froz = Field()

        class Unrelated:
            field_list = [mock.Mock('fake_field')]

        with mock.patch.object(self.fc, 'add_field') as mock_add_field:
            self.fc.inspect_base_classes((Base1, Base2, Unrelated))
            mock_add_field.assert_has_calls([
                ((Base1.foo, 'Base1'), {}),
                ((Base1.bar, 'Base1'), {}),
                ((Base2.froz, 'Base2'), {}),
            ])

    def test_inspect_namespace_calls_add_field(self):
        """
        .inspect_namespace() calls add_field() on each Field
        """
        with mock.patch.object(self.fc, 'add_field') as mock_add_field:
            self.fc.inspect_namespace(self.ns, 'cls')
        mock_add_field.assert_has_call(self.foo, 'cls')
        mock_add_field.assert_has_call(self.bar, 'cls')

    def test_inspect_namespace_sets_field_name(self):
        """
        .inspect_namespace() sets the .name attribute of each field.
        """
        self.assertIsNone(self.foo.name)
        self.assertIsNone(self.bar.name)
        fc = _FieldCollection()
        fc.inspect_namespace(self.ns, 'cls')
        self.assertEqual(self.foo.name, 'foo')
        self.assertEqual(self.bar.name, 'bar')

    def test_inspect_namespace_sets_field_instance_attr(self):
        """
        .inspect_namespace() sets the .instance_attr attribute of each field.
        """
        self.assertIsNone(self.foo.instance_attr)
        self.assertIsNone(self.bar.instance_attr)
        fc = _FieldCollection()
        fc.inspect_namespace(self.ns, 'cls')
        self.assertEqual(self.foo.instance_attr, '_foo')
        self.assertEqual(self.bar.instance_attr, '_bar')


class PODTests(TestCase):

    def test_field_list(self):
        """
        Test that PODMeta correctly set up the field_list attribute
        """
        m = mock.Mock()

        class T(POD):
            f1 = Field()
            f2 = Field(initial='default')
            f3 = Field(initial_fn=lambda: m())

        self.assertEqual(T.field_list, [T.f1, T.f2, T.f3])

    def test_namedtuple_cls(self):
        """
        Test that PODMeta correctly set up the namedtuple_cls attribute
        """
        m = mock.Mock()

        class T(POD):
            f1 = Field()
            f2 = Field(initial='default')
            f3 = Field(initial_fn=lambda: m())

        self.assertEqual(T.namedtuple_cls.__name__, 'T')
        self.assertIsInstance(T.namedtuple_cls.f1, property)
        self.assertIsInstance(T.namedtuple_cls.f2, property)
        self.assertIsInstance(T.namedtuple_cls.f3, property)

    def test_initializer_positional_arguments(self):
        """
        Test initializer operation with positional arguments
        """
        m = mock.Mock()

        class T(POD):
            f1 = Field()
            f2 = Field(initial='default')
            f3 = Field(initial_fn=lambda: m())

        self.assertEqual(T().f1, None)
        self.assertEqual(T().f2, "default")
        self.assertEqual(T().f3, m())
        self.assertEqual(T(1).f1, 1)
        self.assertEqual(T(1).f2, 'default')
        self.assertEqual(T(1).f3, m())
        self.assertEqual(T(1, 2).f1, 1)
        self.assertEqual(T(1, 2).f2, 2)
        self.assertEqual(T(1, 2, 3).f3, 3)

    def test_initializer_keyword_arguments(self):
        """
        Test initializer operation with positional arguments
        """
        m = mock.Mock()

        class T(POD):
            f1 = Field()
            f2 = Field(initial='default')
            f3 = Field(initial_fn=lambda: m())

        self.assertEqual(T().f1, None)
        self.assertEqual(T().f2, "default")
        self.assertEqual(T().f3, m())
        self.assertEqual(T(f1=1).f1, 1)
        self.assertEqual(T(f1=1).f2, 'default')
        self.assertEqual(T(f1=1).f3, m())
        self.assertEqual(T(f1=1, f2=2).f1, 1)
        self.assertEqual(T(f1=1, f2=2).f2, 2)
        self.assertEqual(T(f1=1, f2=2).f3, m())
        self.assertEqual(T(f1=1, f2=2, f3=3).f1, 1)
        self.assertEqual(T(f1=1, f2=2, f3=3).f2, 2)
        self.assertEqual(T(f1=1, f2=2, f3=3).f3, 3)

    def test_initializer_mandatory_arguments(self):
        """
        Test initializer's response to mishandling of MANDATORY fields
        """
        class T(POD):
            m1 = Field(initial=MANDATORY)
            m2 = Field(initial=MANDATORY)

        with self.assertRaisesRegex(
                TypeError, "mandatory argument missing: m1"):
            T()
        with self.assertRaisesRegex(
                TypeError, "mandatory argument missing: m1"):
            T(m2=2)
        with self.assertRaisesRegex(
                TypeError, "mandatory argument missing: m2"):
            T(1)
        with self.assertRaisesRegex(
                TypeError, "mandatory argument missing: m2"):
            T(m1=1)

    def test_initializer_default_arguments(self):
        """
        Test initializer's response to default values
        """
        class T(POD):
            f = Field(initial=42)
        self.assertEqual(T().f, 42)
        self.assertEqual(T(1).f, 1)
        self.assertEqual(T(f=1).f, 1)

    def test_initializer_duplicate_field_value(self):
        """
        Test that double initialization is not permitted
        """
        class T(POD):
            f = Field()
        with self.assertRaisesRegex(
                TypeError, "field initialized twice: f"):
            T(1, f=2)

    def test_initializer_unknown_field(self):
        """
        Test that initializing unknown fields is not permitted
        """
        class T(POD):
            pass
        with self.assertRaisesRegex(TypeError, "too many arguments"):
            T(1)
        with self.assertRaisesRegex(TypeError, "no such field: f"):
            T(f=1)

    def test_smoke(self):
        """
        Test that a simple Person POD can be used to demonstrate basic features
        """
        class Person(POD):
            name = Field()
            age = Field()

            def __str__(self):
                return 'Mr. {}'.format(self.name)

        class Employee(Person):
            salary = Field()

        self.assertEqual(
            Person.field_list, [Person.name, Person.age])
        joe = Employee('Joe')
        # Methods still work
        self.assertEqual(str(joe), 'Mr. Joe')
        # Reading attributes works
        self.assertEqual(joe.name, 'Joe')
        self.assertEqual(joe.age, None)
        # Setting attributes works
        joe.age = 42
        self.assertEqual(joe.age, 42)
        joe.salary = 1000
        self.assertEqual(joe.salary, 1000)
        # Comparison to other PODs works
        self.assertEqual(joe, Employee('Joe', 42, 1000))
        self.assertLess(joe, Employee('Joe', 45, 1000))
        # The .as_{tuple,dict}() methods work
        self.assertEqual(joe.as_tuple(), ('Joe', 42, 1000))
        self.assertEqual(
            joe.as_dict(), {'name': 'Joe', 'age': 42, 'salary': 1000})
        # The return value of repr is useful
        self.assertEqual(
            repr(joe), "Employee(name='Joe', age=42, salary=1000)")

    def test_notifications(self):
        """
        Test that change notifications get sent
        """
        class T(POD):
            f = Field(notify=True)

        field_callback = mock.Mock(name='field_callback')
        # Create a POD and connect signal listeners
        pod = T()
        pod.on_f_changed.connect(field_callback)
        # Modify a field
        pod.f = 1
        # Ensure the modification worked
        self.assertEqual(pod.f, 1)
        # Ensure signals fired
        field_callback.assert_called_with(None, 1)

    def test_pod_inheritance(self):

        class B(POD):
            f1 = Field(notify=True)

        class D(B):
            f2 = Field()

        # D doesn't shadow B.f1
        self.assertIs(B.on_f1_changed, D.on_f1_changed)
        # B and D has correct field lists
        self.assertEqual(B.field_list, [B.f1])
        self.assertEqual(D.field_list, [B.f1, D.f2])

    def test_pod_ordering(self):
        """
        POD comparison doesn't care about the field names
        """

        class A(POD):
            a = Field()

        B = A  # easier to understand subsequent testds
        self.assertTrue(A(1) == B(1))
        self.assertTrue(A(1) != B(0))
        self.assertTrue(A(0) < B(1))
        self.assertTrue(A(1) > B(0))
        self.assertTrue(A(1) >= B(1))
        self.assertTrue(A(1) <= B(1))

    def test_pod_ordering_tricky1(self):
        """
        POD comparison doesn't care about actual classes
        """

        class A(POD):
            f = Field()

        class B(POD):
            f = Field()

        self.assertTrue(A(1) == B(1))
        self.assertTrue(A(1) != B(0))
        self.assertTrue(A(0) < B(1))
        self.assertTrue(A(1) > B(0))
        self.assertTrue(A(1) >= B(1))
        self.assertTrue(A(1) <= B(1))

    def test_pod_ordering_tricky2(self):
        """
        POD comparison doesn't care about the field names
        """

        class A(POD):
            a = Field()

        class B(POD):
            b = Field()

        self.assertTrue(A(1) == B(1))
        self.assertTrue(A(1) != B(0))
        self.assertTrue(A(0) < B(1))
        self.assertTrue(A(1) > B(0))
        self.assertTrue(A(1) >= B(1))
        self.assertTrue(A(1) <= B(1))

    def test_pod_ordering_other_types(self):
        """
        POD comparison understands other types and is not equal to them
        """

        class A(POD):
            f = Field()

        self.assertFalse(A(1) == (1,))
        self.assertFalse(A(1) == [1])
        self.assertFalse(A(1) == 1)
