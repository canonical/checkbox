from plainbox.impl.new_resource import evaluate, evaluate_lazy, UnknownResource
from unittest import TestCase

class HashableDict(dict):
    def __hash__(self):
        return hash(frozenset(self.items()))

HD = HashableDict

class TestEvaluateEndToEnd(TestCase):
    def test_equal_true(self):
        expr = "(namespace.a == 1)"
        namespace = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}
        result = {"namespace": [HD({"a": 1, "b": 2})]}
        result_bool = True

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

        evaluated = all(evaluate_lazy(expr, namespace).values())
        self.assertEqual(evaluated, result_bool)

    def test_commutative(self):
        expr = "(1 == namespace.a)"
        namespace = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}
        result = {"namespace": [HD({"a": 1, "b": 2})]}
        result_bool = True

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

        evaluated = all(evaluate_lazy(expr, namespace).values())
        self.assertEqual(evaluated, result_bool)


    def test_equal_false(self):
        expr = "(namespace.a == 3)"
        namespace = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}
        result = {"namespace": []}
        result_bool = False

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

        evaluated = all(evaluate_lazy(expr, namespace).values())
        self.assertEqual(evaluated, result_bool)

    def test_and_true(self):
        expr = "namespace.b == 2 and namespace.a == 1"
        namespace = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}
        result = {"namespace": [HD({"a": 1, "b": 2})]}
        result_bool = True

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

        evaluated = all(evaluate_lazy(expr, namespace).values())
        self.assertEqual(evaluated, result_bool)

    def test_and_false(self):
        expr = "namespace.b == -1 and namespace.a == 1"
        namespace = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}
        result = {"namespace": []}
        result_bool = False

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

        evaluated = all(evaluate_lazy(expr, namespace).values())
        self.assertEqual(evaluated, result_bool)

    def test_or_true(self):
        expr = "namespace.b == 2 or namespace.a == 1"
        namespace = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}
        result = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}
        result_bool = True

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

        evaluated = all(evaluate_lazy(expr, namespace).values())
        self.assertEqual(evaluated, result_bool)

    def test_or_true_regression(self):
        expr = "namespace.a == 1 and (namespace.b == -2 or namespace.a == 1)"
        namespace = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}
        result = {"namespace": [HD({"a": 1, "b": 2})]}
        result_bool = True

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

        evaluated = all(evaluate_lazy(expr, namespace).values())
        self.assertEqual(evaluated, result_bool)

    def test_or_false(self):
        expr = "namespace.b == 20 or namespace.a == 11"
        namespace = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}
        result = {"namespace": []}
        result_bool = False

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

        evaluated = all(evaluate_lazy(expr, namespace).values())
        self.assertEqual(evaluated, result_bool)

    def test_gt_true(self):
        expr = "namespace.a > 1"
        namespace = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}
        result = {"namespace": [HD({"a": 2, "b": 2})]}
        result_bool = True

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

        evaluated = all(evaluate_lazy(expr, namespace).values())
        self.assertEqual(evaluated, result_bool)

    def test_gt_false(self):
        expr = "namespace.a > 10"
        namespace = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}
        result = {"namespace": []}
        result_bool = False

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

        evaluated = all(evaluate_lazy(expr, namespace).values())
        self.assertEqual(evaluated, result_bool)

    def test_gte(self):
        expr = "namespace.a >= 1"
        namespace = {
            "namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})],
        }
        result = {"namespace": [HD({"a": 1, "b": 2}), HD({"a": 2, "b": 2})]}

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

    def test_cast_int(self):
        expr = "int(namespace.a) == 1"
        namespace = {
            "namespace": [HD({"a": "1", "b": "2"}), HD({"a": "2", "b": "2"})],
        }
        result = {"namespace": [HD({"a": "1", "b": "2"})]}

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

    def test_cast_float(self):
        expr = "float(namespace.a) == 1"
        namespace = {
            "namespace": [HD({"a": "1", "b": "2"}), HD({"a": "2", "b": "2"})],
        }
        result = {"namespace": [HD({"a": "1", "b": "2"})]}

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

    def test_in(self):
        expr = "namespace.a in ['1', '2']"
        namespace = {"namespace": [HD({"a": "1"}), HD({"a": "2"}), HD({"a": "3"})]}
        result = {"namespace": [HD({"a": "1"}), HD({"a": "2"})]}

        evaluated = evaluate(expr, namespace)
        self.assertEqual(evaluated, result)

    def test_in_tuple(self):
        expr = "namespace.a in ('1', '2')"
        namespace = {"namespace": [HD({"a": "1"}), HD({"a": "2"}), HD({"a": "3"})]}
        result = {"namespace": [HD({"a": "1"}), HD({"a": "2"})]}

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

    def test_neq_true(self):
        expr = "namespace.a != '1'"
        namespace = {"namespace": [HD({"a": "1"}), HD({"a": "2"}), HD({"a": "3"})]}
        result = {"namespace": [HD({"a": "2"}), HD({"a": "3"})]}

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

    def test_neq_false(self):
        expr = (
            "namespace.a != '1' and namespace.a != '2' and namespace.a != '3'"
        )
        namespace = {"namespace": [HD({"a": "1"}), HD({"a": "2"})]}
        result = {"namespace": []}

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

    def test_multiple_or(self):
        expr = "namespace.a == '1' or namespace.a == '2' or namespace.a == '3'"
        namespace = {"namespace": [HD({"a":"1"}), HD({"a": "2"}), HD({"a": "3"})]}
        result = {"namespace": [HD({"a": "1"}), HD({"a": "2"}), HD({"a": "3"})]}

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

    def test_implicit_namespace_eq(self):
        expr = "(namespace.a == 3)"
        namespace = {
            "com.canonical.certification::namespace": [
                HD({"a": 1, "b": 2}),
                HD({"a": 2, "b": 2}),
            ]
        }
        result = {"com.canonical.certification::namespace": []}
        result_bool = False

        evaluated = evaluate(
            expr,
            namespace,
            explain_callback=print,
            implicit_namespace="com.canonical.certification",
        )

        self.assertEqual(evaluated, result)

        evaluated = all(
            evaluate_lazy(
                expr,
                namespace,
                implicit_namespace="com.canonical.certification",
            ).values()
        )
        self.assertEqual(evaluated, result_bool)

    def test_default_namespace_eq(self):
        expr = "manifest.has_usbc == 'True'"
        namespace = {
            "com.canonical.certification::namespace": [
                HD({"a": 1, "b": 2}),
                HD({"a": 2, "b": 2}),
            ],
            "com.canonical.plainbox::manifest": [HD({"has_usbc": "True"})],
        }
        result = {
            "com.canonical.certification::namespace": [
                HD({"a": 1, "b": 2}),
                HD({"a": 2, "b": 2}),
            ],
            "com.canonical.plainbox::manifest": [HD({"has_usbc": "True"})],
        }
        result_bool = True

        evaluated = evaluate(
            expr,
            namespace,
            explain_callback=print,
            implicit_namespace="com.canonical.certification",
        )
        self.assertEqual(evaluated, result)

        evaluated = all(
            evaluate_lazy(
                expr,
                namespace,
                implicit_namespace="com.canonical.certification",
            ).values()
        )
        self.assertEqual(evaluated, result_bool)

    def test_empty_resource_false(self):
        expr = "namespace.tmp == 1"
        namespace = {}

        with self.assertRaises(UnknownResource):
            _ = evaluate(
                expr,
                namespace,
            )

        with self.assertRaises(UnknownResource):
            self.assertFalse(
                all(evaluate_lazy(expr, namespace).values())
            )
