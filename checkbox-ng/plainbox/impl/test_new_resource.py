from plainbox.impl.new_resource import evaluate, evaluate_lazy, UnknownResource
from unittest import TestCase


class HashableDict(dict):
    def __hash__(self):
        return hash(frozenset(self.items()))


HD = HashableDict


class TestEvaluateEndToEnd(TestCase):
    """
    Note: all tests here use non-string values just to make the code easier to
          follow. In reality all values in resource expressions are strings so
          one has to cast them to compare them
    """

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
        namespace = {
            "namespace": [HD({"a": "1"}), HD({"a": "2"}), HD({"a": "3"})]
        }
        result = {"namespace": [HD({"a": "1"}), HD({"a": "2"})]}

        evaluated = evaluate(expr, namespace)
        self.assertEqual(evaluated, result)

    def test_in_tuple(self):
        expr = "namespace.a in ('1', '2')"
        namespace = {
            "namespace": [HD({"a": "1"}), HD({"a": "2"}), HD({"a": "3"})]
        }
        result = {"namespace": [HD({"a": "1"}), HD({"a": "2"})]}

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

    def test_neq_true(self):
        expr = "namespace.a != '1'"
        namespace = {
            "namespace": [HD({"a": "1"}), HD({"a": "2"}), HD({"a": "3"})]
        }
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
        namespace = {
            "namespace": [HD({"a": "1"}), HD({"a": "2"}), HD({"a": "3"})]
        }
        result = {
            "namespace": [HD({"a": "1"}), HD({"a": "2"}), HD({"a": "3"})]
        }

        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

    def test_implicit_namespace_eq(self):
        expr = "(namespace.a == 3)"
        namespace = {
            "com.canonical.certification::namespace": [
                HD({"a": 1, "b": 2}),
                HD({"a": 2, "b": 2}),
                HD({"a": 3, "b": 2}),
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

        result = {
            "com.canonical.certification::namespace": [HD({"a": 3, "b": 2})]
        }
        result_bool = True

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
            all(evaluate_lazy(expr, namespace).values())

    def test_const_fetching(self):
        expr = "dmi.product in DESKTOP_PC_PRODUCT"
        namespace = {
            "dmi": [HD({"product": "All In One"}), HD({"product": "Laptop"})]
        }
        result = {"dmi": [HD({"product": "All In One"})]}

        self.assertEqual(
            evaluate(expr, namespace, explain_callback=print),
            result,
        )

        self.assertTrue(all(evaluate_lazy(expr, namespace).values()))

    def test_nested_and_or_combination(self):
        expr = (
            "(namespace.a == 1 and namespace.b == 2) "
            "or (namespace.c == 3 and namespace.d == 4)"
        )
        namespace = {
            "namespace": [
                HD({"a": 1, "b": 2, "c": 0, "d": 0}),  # First condition true
                HD({"a": 0, "b": 0, "c": 3, "d": 4}),  # Second condition true
                HD({"a": 0, "b": 0, "c": 0, "d": 0}),  # Neither condition true
            ]
        }
        result = {
            "namespace": [
                HD({"a": 1, "b": 2, "c": 0, "d": 0}),
                HD({"a": 0, "b": 0, "c": 3, "d": 4}),
            ]
        }
        evaluated = evaluate(expr, namespace)
        self.assertEqual(evaluated, result)

    def test_string_contains(self):
        expr = "'hello' in namespace.text"
        namespace = {
            "namespace": [
                HD({"text": "hello world"}),
                HD({"text": "goodbye world"}),
                HD({"text": "HELLO WORLD"}),  # Case sensitive
            ]
        }
        result = {"namespace": [HD({"text": "hello world"})]}
        evaluated = evaluate(expr, namespace)
        self.assertEqual(evaluated, result)

    def test_multiple_namespaces_and(self):
        expr = "ns1.value == 1 and ns2.value == 2"
        namespace = {
            "ns1": [HD({"value": 1}), HD({"value": 2})],
            "ns2": [HD({"value": 2}), HD({"value": 3})],
        }
        result = {
            "ns1": [HD({"value": 1})],
            "ns2": [HD({"value": 2})],
        }
        evaluated = evaluate(expr, namespace)
        self.assertEqual(evaluated, result)

    def test_complex_nested_logic(self):
        expr = "(namespace.c == 3 and (namespace.d == 4 or namespace.d == 5))"
        namespace = {
            "namespace": [
                HD({"a": 0, "b": 0, "c": 3, "d": 4}),  # First condition (d==4)
                HD(
                    {"a": 0, "b": 0, "c": 3, "d": 5}
                ),  # Second condition (d==5)
                HD({"a": 1, "b": 2, "c": 0, "d": 0}),  # No match
                HD({"a": 0, "b": 0, "c": 3, "d": 6}),  # No match
            ]
        }
        result = {
            "namespace": [
                HD({"a": 0, "b": 0, "c": 3, "d": 4}),
                HD({"a": 0, "b": 0, "c": 3, "d": 5}),
            ]
        }
        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)

    def test_multiple_namespace_complex_condition(self):
        expr = (
            "(ns1.value > 10 and ns2.text == 'hello') "
            "or (ns1.value < 5 and ns2.text == 'world')"
        )
        namespace = {
            "ns1": [
                HD({"value": 15}),
                HD({"value": 3}),
                HD({"value": 7}),
            ],
            "ns2": [
                HD({"text": "hello"}),
                HD({"text": "world"}),
                HD({"text": "other"}),
            ],
        }
        result = {
            "ns1": [HD({"value": 15}), HD({"value": 3})],
            "ns2": [HD({"text": "hello"}), HD({"text": "world"})],
        }
        evaluated = evaluate(expr, namespace, explain_callback=print)
        self.assertEqual(evaluated, result)
