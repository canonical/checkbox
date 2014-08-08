# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
plainbox.impl.test_resource
===========================

Test definitions for plainbox.impl.resouce module
"""

import ast
from unittest import TestCase

from plainbox.impl.resource import CodeNotAllowed
from plainbox.impl.resource import ExpressionCannotEvaluateError
from plainbox.impl.resource import ExpressionFailedError
from plainbox.impl.resource import FakeResource
from plainbox.impl.resource import MultipleResourcesReferenced
from plainbox.impl.resource import NoResourcesReferenced
from plainbox.impl.resource import Resource
from plainbox.impl.resource import ResourceExpression
from plainbox.impl.resource import ResourceNodeVisitor
from plainbox.impl.resource import ResourceProgram
from plainbox.impl.resource import ResourceProgramError
from plainbox.impl.resource import ResourceSyntaxError


class ExpressionFailedTests(TestCase):

    def test_smoke(self):
        expression = ResourceExpression('resource.attr == "value"')
        exc = ExpressionFailedError(expression)
        self.assertIs(exc.expression, expression)
        self.assertEqual(str(exc), (
            "expression 'resource.attr == \"value\"' evaluated to a non-true"
            " result"))
        self.assertEqual(repr(exc), (
            "<ExpressionFailedError expression:<ResourceExpression"
            " text:'resource.attr == \"value\"'>>"))


class ExpressionCannotEvaluateErrorTests(TestCase):

    def test_smoke(self):
        expression = ResourceExpression('resource.attr == "value"')
        exc = ExpressionCannotEvaluateError(expression)
        self.assertIs(exc.expression, expression)
        self.assertEqual(str(exc), (
            "expression 'resource.attr == \"value\"' needs unavailable"
            " resource 'resource'"))
        self.assertEqual(repr(exc), (
            "<ExpressionCannotEvaluateError expression:<ResourceExpression"
            " text:'resource.attr == \"value\"'>>"))


class ResourceTests(TestCase):

    def test_init(self):
        res = Resource()
        self.assertEqual(self._get_private_data(res), {})
        res = Resource({'attr': 'value'})
        self.assertEqual(self._get_private_data(res), {'attr': 'value'})

    def test_private_data_is_somewhat_protected(self):
        res = Resource()
        self.assertRaises(AttributeError, getattr, res, "_data")
        self.assertRaises(AttributeError, delattr, res, "_data")
        self.assertRaises(AttributeError, setattr, res, "_data", None)

    def test_private_data_is_not_that_protected(self):
        res = Resource()
        data = self._get_private_data(res)
        self.assertEqual(data, {})
        data['attr'] = 'value'
        self.assertEqual(res.attr, 'value')

    def test_getattr(self):
        res = Resource()
        self.assertRaises(AttributeError, getattr, res, "attr")
        res = Resource({'attr': 'value'})
        self.assertEqual(getattr(res, 'attr'), 'value')

    def test_getitem(self):
        res = Resource()
        self.assertRaises(KeyError, lambda res: res["attr"], res)
        res = Resource({'attr': 'value'})
        self.assertEqual(res['attr'], 'value')

    def test_setattr(self):
        res = Resource()
        res.attr = 'value'
        self.assertEqual(res.attr, 'value')
        res.attr = 'other value'
        self.assertEqual(res.attr, 'other value')

    def test_setitem(self):
        res = Resource()
        res['attr'] = 'value'
        self.assertEqual(res['attr'], 'value')
        res['attr'] = 'other value'
        self.assertEqual(res['attr'], 'other value')

    def test_delattr(self):
        res = Resource()
        self.assertRaises(AttributeError, delattr, res, "attr")
        res = Resource({'attr': 'value'})
        del res.attr
        self.assertRaises(AttributeError, getattr, res, "attr")
        self.assertRaises(AttributeError, lambda res: res.attr, res)

    def test_delitem(self):
        res = Resource()
        with self.assertRaises(KeyError):
            del res["attr"]
        res = Resource({'attr': 'value'})
        del res['attr']
        self.assertRaises(KeyError, lambda res: res['attr'], res)

    def test_repr(self):
        self.assertEqual(repr(Resource()), "Resource({})")
        self.assertEqual(repr(Resource({'attr': 'value'})),
                         "Resource({'attr': 'value'})")

    def test_eq(self):
        self.assertEqual(Resource(), Resource())
        self.assertEqual(Resource({'attr': 'value'}),
                         Resource({'attr': 'value'}))
        self.assertFalse(Resource() == object())

    def test_ne(self):
        self.assertNotEqual(Resource({'attr': 'value'}),
                            Resource({'attr': 'other value'}))
        self.assertNotEqual(Resource({'attr': 'value'}),
                            Resource())
        self.assertTrue(Resource() != object())

    def _get_private_data(self, res):
        return object.__getattribute__(res, '_data')


class FakeResourceTests(TestCase):

    def test_resource_attributes(self):
        """
        Verify that any accessed attribute / item resolves to its name
        """
        resource = FakeResource()
        self.assertEqual(resource.foo, 'foo')
        self.assertEqual(resource['bar'], 'bar')

    def test_set_membership(self):
        """
        Verify that any item is present
        """
        self.assertTrue('foo' in FakeResource())

    def test_tracking_support(self):
        """
        Verify that each accessed attribute / item is remembered
        """
        accessed = set()
        resource = FakeResource(accessed)
        self.assertEqual(resource.foo, 'foo')
        self.assertEqual(resource['bar'], 'bar')
        self.assertEqual(accessed, {'foo', 'bar'})


class ResourceProgramErrorTests(TestCase):

    def test_multiple(self):
        exc = MultipleResourcesReferenced()
        self.assertEqual(
            str(exc), "expression referenced multiple resources")

    def test_none(self):
        exc = NoResourcesReferenced()
        self.assertEqual(
            str(exc), "expression did not reference any resources")


class CodeNotAllowedTests(TestCase):

    def test_smoke(self):
        node = ast.parse("foo")
        exc = CodeNotAllowed(node)
        self.assertIs(exc.node, node)

    def test_inheritance(self):
        self.assertTrue(issubclass(CodeNotAllowed, ResourceProgramError))


class ResourceNodeVisitorTests(TestCase):

    def test_smoke(self):
        visitor = ResourceNodeVisitor()
        self.assertEqual(visitor.ids_seen, set())

    def test_ids_seen(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("package.name == 'fwts' and package.version == '1.2'")
        visitor.visit(node)
        self.assertEqual(visitor.ids_seen, {'package'})

    def test_name_assignment_disallowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("package = 'fwts'")
        self.assertRaises(CodeNotAllowed, visitor.visit, node)

    def test_attribute_assignment_disallowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("package.name = 'fwts'")
        self.assertRaises(CodeNotAllowed, visitor.visit, node)

    def test_slice_assignment_disallowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("package[:] = 'fwts'")
        self.assertRaises(CodeNotAllowed, visitor.visit, node)

    def test_index_assignment_disallowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("package[0] = 'fwts'")
        self.assertRaises(CodeNotAllowed, visitor.visit, node)

    def test_raising_disallowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("raise foo")
        self.assertRaises(CodeNotAllowed, visitor.visit, node)

    def test_importing_disallowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("import foo")
        self.assertRaises(CodeNotAllowed, visitor.visit, node)

    def test_function_calls_disallowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("foo()")
        self.assertRaises(CodeNotAllowed, visitor.visit, node)

    def test_calling_int_is_allowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("len(a)")
        visitor.visit(node)

    def test_calling_len_is_allowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("int('10')")
        visitor.visit(node)

    def test_boolean_ops_are_allowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("package.name and package.version")
        visitor.visit(node)

    def test_comparisons_are_allowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("package.name == 'foo'")
        visitor.visit(node)

    def test_in_expresions_are_allowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("'foo' in package.name")
        visitor.visit(node)

    def test_in_expresions_with_list_are_allowed(self):
        visitor = ResourceNodeVisitor()
        node = ast.parse("package.name in ['foo', 'bar']")
        visitor.visit(node)


class ResourceExpressionTests(TestCase):

    def test_smoke_good(self):
        text = "package.name == 'fwts'"
        expr = ResourceExpression(text)
        self.assertEqual(expr.text, text)
        self.assertEqual(expr.resource_id, "package")
        self.assertEqual(expr.implicit_namespace, None)

    def test_namespace_support(self):
        text = "package.name == 'fwts'"
        expr = ResourceExpression(text, "2014.com.canonical")
        self.assertEqual(expr.text, text)
        self.assertEqual(expr.resource_id, "2014.com.canonical::package")
        self.assertEqual(expr.implicit_namespace, "2014.com.canonical")

    def test_imports_support(self):
        text = "package.name == 'fwts'"
        expr1 = ResourceExpression(text, "2014.com.example")
        self.assertEqual(expr1.text, text)
        self.assertEqual(expr1.resource_id, "2014.com.example::package")
        self.assertEqual(expr1.implicit_namespace, "2014.com.example")
        expr2 = ResourceExpression(text, "2014.com.example", imports=())
        self.assertEqual(expr2.text, text)
        self.assertEqual(expr2.resource_id, "2014.com.example::package")
        self.assertEqual(expr2.implicit_namespace, "2014.com.example")
        expr3 = ResourceExpression(
            text, "2014.com.example", imports=[
                ('2014.com.canonical::package', 'package')])
        self.assertEqual(expr3.text, text)
        self.assertEqual(expr3.resource_id, "2014.com.canonical::package")
        self.assertEqual(expr3.implicit_namespace, "2014.com.example")

    def test_smoke_bad(self):
        self.assertRaises(ResourceSyntaxError, ResourceExpression, "barf'")
        self.assertRaises(CodeNotAllowed, ResourceExpression, "a = 5")
        self.assertRaises(NoResourcesReferenced, ResourceExpression, "5 < 10")
        self.assertRaises(MultipleResourcesReferenced,
                          ResourceExpression, "a.foo == 1 and b.bar == 2")

    def test_evaluate_no_namespaces(self):
        self.assertFalse(ResourceExpression("whatever").evaluate([]))

    def test_evaluate_normal(self):
        # NOTE: the actual expr.resource_id is irrelevant for this test
        expr = ResourceExpression("obj.a == 2")
        self.assertTrue(
            expr.evaluate([
                Resource({'a': 1}), Resource({'a': 2})]))
        self.assertTrue(
            expr.evaluate([
                Resource({'a': 2}), Resource({'a': 1})]))
        self.assertFalse(
            expr.evaluate([
                Resource({'a': 1}), Resource({'a': 3})]))

    def test_evaluate_exception(self):
        # NOTE: the actual expr.resource_id is irrelevant for this test
        expr = ResourceExpression("obj.a == 2")
        self.assertFalse(expr.evaluate([Resource()]))

    def test_evaluate_checks_resource_type(self):
        expr = ResourceExpression("obj.a == 2")
        self.assertRaises(TypeError, expr.evaluate, [{'a': 2}])


class ResourceProgramTests(TestCase):

    def setUp(self):
        super(ResourceProgramTests, self).setUp()
        self.prog = ResourceProgram(
            "\n"  # empty lines are ignored
            "package.name == 'fwts'\n"
            "platform.arch in ('i386', 'amd64')")

    def test_expressions(self):
        self.assertEqual(len(self.prog.expression_list), 2)
        self.assertEqual(self.prog.expression_list[0].text,
                         "package.name == 'fwts'")
        self.assertEqual(self.prog.expression_list[0].resource_id,
                         "package")
        self.assertEqual(self.prog.expression_list[1].text,
                         "platform.arch in ('i386', 'amd64')")
        self.assertEqual(self.prog.expression_list[1].resource_id,
                         "platform")

    def test_required_resources(self):
        self.assertEqual(self.prog.required_resources,
                         set(('package', 'platform')))

    def test_evaluate_failure_not_true(self):
        resource_map = {
            'package': [
                Resource({'name': 'plainbox'}),
            ],
            'platform': [
                Resource({'arch': 'i386'})]
        }
        with self.assertRaises(ExpressionFailedError) as call:
            self.prog.evaluate_or_raise(resource_map)
        self.assertEqual(call.exception.expression.text,
                         "package.name == 'fwts'")

    def test_evaluate_without_no_match(self):
        resource_map = {
            'package': [],
            'platform': []
        }
        with self.assertRaises(ExpressionFailedError) as call:
            self.prog.evaluate_or_raise(resource_map)
        self.assertEqual(call.exception.expression.text,
                         "package.name == 'fwts'")

    def test_evaluate_failure_no_resource(self):
        resource_map = {
            'platform': [
                Resource({'arch': 'i386'})]
        }
        with self.assertRaises(ExpressionCannotEvaluateError) as call:
            self.prog.evaluate_or_raise(resource_map)
        self.assertEqual(call.exception.expression.text,
                         "package.name == 'fwts'")

    def test_evaluate_success(self):
        resource_map = {
            'package': [
                Resource({'name': 'plainbox'}),
                Resource({'name': 'fwts'})],
            'platform': [
                Resource({'arch': 'i386'})]
        }
        self.assertTrue(self.prog.evaluate_or_raise(resource_map))

    def test_namespace_support(self):
        prog = ResourceProgram(
            "package.name == 'fwts'\n"
            "platform.arch in ('i386', 'amd64')",
            implicit_namespace="2014.com.canonical")
        self.assertEqual(
            prog.required_resources,
            {'2014.com.canonical::package', '2014.com.canonical::platform'})
