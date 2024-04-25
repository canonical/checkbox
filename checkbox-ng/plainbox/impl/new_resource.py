import os
import ast
import operator
import itertools
import functools

from copy import copy


class HashableDict(dict):
    def __hash__(self):
        return hash(frozenset(self.items()))


HD = HashableDict


class Constraint:
    def __init__(self, left_getter, operator, right_getter):
        if isinstance(left_getter, NamespacedGetter) and isinstance(
            right_getter, NamespacedGetter
        ):
            raise ValueError(
                "Unsupported comparison of namespaces with operands {} and {}".format(
                    left_getter, right_getter
                )
            )
        self.left_getter = left_getter
        self.operator = operator
        self.right_getter = right_getter
        try:
            self.namespace = self.left_getter.namespace
        except AttributeError:
            self.namespace = self.right_getter.namespace

    @classmethod
    def parse_from_ast(cls, parsed): ...


class ValueGetter:
    """
    A value getter is a getter that returns a value
    that is independent from variables in any namespace
    """


class NamespacedGetter:
    """
    A namespaced getter is a getter who's return value
    is dependent on the current namespace
    """

    def __init__(self, namespace):
        self.namespace = namespace


class CallGetter(NamespacedGetter):
    """
    This is a function call that evaluates over a variable
    in the group over a single namespace
    """

    CALLS_MEANING = {
        "int": int,
        "bool": bool,
        "float": float,
        "str": str,
    }

    def _get_namespace_args(self, args):
        namespace = None
        for arg in args:
            try:
                arg_ns = arg.namespace
                if namespace and arg_ns != namespace:
                    raise ValueError(
                        "Mixed namespaces in function call are not supported ({} != {})".format(
                            namespace, arg_ns
                        )
                    )
                namespace = arg_ns
            except AttributeError:
                ...
        if namespace is None:
            raise ValueError("Function call with no namespace are unsupported")
        return namespace

    def __init__(self, parsed_ast):
        try:
            self.function_name = parsed_ast.func.id
            self.function = self.CALLS_MEANING[parsed_ast.func.id]
        except KeyError:
            raise ValueError(
                "Unsupported function {}".format(parsed_ast.func.id)
            )

        self.args = [getter_from_ast(arg) for arg in parsed_ast.args]
        self.namespace = self._get_namespace_args(self.args)

    def __call__(self, variable_group):
        return self.function(*(arg(variable_group) for arg in self.args))

    def __str__(self):
        args = ",".join(str(x) for x in self.args)
        return f"{self.function_name}({args})"


class AttributeGetter(NamespacedGetter):
    def __init__(self, parsed_ast):
        self.namespace = parsed_ast.value.id
        self.variable = parsed_ast.attr

    def __call__(self, variable_group):
        # resources are free form, support variable names not being unifrom
        try:
            return variable_group[self.variable]
        except KeyError:
            return None

    def __str__(self):
        return f"{self.namespace}.{self.variable}"


class ConstantGetter(ValueGetter):
    def __init__(self, parsed_ast):
        self.value = parsed_ast.value

    def __call__(self, *args):
        return self.value

    @classmethod
    def from_unary_op(cls, parsed_ast):
        if not isinstance(parsed_ast.op, ast.USub):
            raise ValueError("Unsupported operator {}".format(parsed_ast))
        parsed_ast.operand.value *= -1
        return cls(parsed_ast.operand)

    def __str__(self):
        return f"{self.value}"


class ListGetter(ConstantGetter):
    def __init__(self, parsed_ast):
        values_getters = [getter_from_ast(value) for value in parsed_ast.elts]
        if any(
            isinstance(value, NamespacedGetter) for value in values_getters
        ):
            raise ValueError("Unsupported collection of non-constant values")
        self.value = [value_getter() for value_getter in values_getters]

    def __str__(self):
        to_r = ", ".join(str(x) for x in self.value)
        return "[{}]".format(to_r)


def getter_from_ast(parsed_ast):
    getters = {
        ast.Call: CallGetter,
        ast.Attribute: AttributeGetter,
        ast.Constant: ConstantGetter,
        ast.List: ListGetter,
        ast.Tuple: ListGetter,
        ast.UnaryOp: ConstantGetter.from_unary_op,
    }
    try:
        getter = getters[type(parsed_ast)]
    except KeyError:
        raise ValueError("Unsupported name/value {}".format(parsed_ast))
    return getter(parsed_ast)


class CompareConstraint(Constraint):
    @classmethod
    def parse_from_ast(cls, parsed_ast):
        assert len(parsed_ast.ops) == 1
        assert len(parsed_ast.comparators) == 1
        left_getter = getter_from_ast(parsed_ast.left)
        right_getter = getter_from_ast(parsed_ast.comparators[0])
        return cls(left_getter, parsed_ast.ops[0], right_getter)

    def _filtered(self, ns_variables):
        def act_contains(x, y):
            # contains(a, b) == b in a
            # so we need to swap them around
            return operator.contains(y, x)

        def act_not_contains(x, y):
            return not act_contains(x, y)

        ast_to_operator = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.GtE: operator.ge,
            ast.Gt: operator.gt,
            ast.LtE: operator.le,
            ast.In: act_contains,
            ast.NotIn: act_not_contains,
        }
        try:
            operator_f = ast_to_operator[type(self.operator)]
        except KeyError:
            raise ValueError("Unsupported operator {}".format(self.operator))

        return (
            variable_group
            for variable_group in ns_variables
            if operator_f(
                self.left_getter(variable_group),
                self.right_getter(variable_group),
            )
        )

    def filtered(self, namespaces):
        if self.namespace not in namespaces:
            return namespaces
        namespaces[self.namespace] = self._filtered(namespaces[self.namespace])
        return namespaces


class CompareConstraintExplainer(CompareConstraint):
    def filtered(self, namespaces, max_namespace_items=5):
        namespace = self.left_getter.namespace
        print(
            "Expression:",
            self.left_getter,
            ast.dump(self.operator),
            self.right_getter,
        )
        print("Filtering:", namespace)
        print("  Pre filter: ")
        namespaces[namespace] = list(namespaces[namespace])
        for filtered in namespaces[namespace][:max_namespace_items]:
            print("   ", filtered)
        if len(namespaces[namespace]) > max_namespace_items:
            print("    [...]")
        namespaces = super().filtered(namespaces)
        print("  Post filter: ")
        namespaces[namespace] = list(namespaces[namespace])
        for filtered in namespaces[namespace][:max_namespace_items]:
            print("   ", filtered)
        if len(namespaces[namespace]) > max_namespace_items:
            print("    [...]")
        return namespaces


def chain_uniq(*iterators):
    to_return = itertools.chain(*iterators)
    already_returned = set()
    for item in to_return:
        h_item = hash(item)
        if h_item not in already_returned:
            already_returned.add(h_item)
            yield item


def namespace_union(ns1, ns2):
    return {
        namespace_name: chain_uniq(ns1[namespace_name], ns2[namespace_name])
        for namespace_name in (ns1.keys() | ns2.keys())
    }


def duplicate_namespace(namespace, count):
    duplicated_namespace = {
        x: itertools.tee(y, count) for (x, y) in namespace.items()
    }
    namespaces = [
        {key: duplicated_namespace[key][i] for key in duplicated_namespace}
        for i in range(count)
    ]
    return namespaces


def eval_bool_op(bool_op, namespace):
    if isinstance(bool_op.op, ast.And):
        return functools.reduce(
            lambda ns, constraint: _act_eval(constraint, ns),
            bool_op.values,
            namespace,
        )
    elif isinstance(bool_op.op, ast.Or):
        duplicated_namespaces = duplicate_namespace(
            namespace, len(bool_op.values)
        )
        ns_constraint = zip(duplicated_namespaces, bool_op.values)
        filtered_namespaces = (
            _act_eval(constraint, namespace)
            for namespace, constraint in ns_constraint
        )
        return functools.reduce(namespace_union, filtered_namespaces)
    raise ValueError("Unsupported bool operator {}".format(namespace))

if os.getenv("RESEXPR_EXPLAIN") == "1":
    CC = CompareConstraintExplainer
else:
    CC = CompareConstraint

def _act_eval(parsed_expr, namespace):
    to_eval = [parsed_expr]

    while to_eval:
        curr = to_eval.pop()
        if isinstance(curr, ast.Expression):
            to_eval.append(curr.body)
        elif isinstance(curr, ast.Compare):  # assume compare is a leaf
            cc = CC.parse_from_ast(curr)
            return cc.filtered(namespace)
        elif isinstance(curr, ast.BoolOp):
            return eval_bool_op(curr, namespace)
        else:
            breakpoint()
    ...

def act_eval(parsed_expr, namespace):
    return _act_eval(parsed_expr, copy(namespace))

def prepare_eval_parse(expr, namespace):
    parsed_expr = ast.parse(expr, mode="eval")
    #print(ast.dump(parsed_expr))
    return act_eval(parsed_expr, copy(namespace))


def evaluate_lazy(namespace):
    def any_next(iterable):
        try:
            next(iterable)
            return True
        except StopIteration:
            return False

    """any_next_ns = {
        namespace_name: any_next(zz)
        for (namespace_name, zz) in namespace.items()
    }"""
    return all(any_next(iter(v)) for v in namespace.values())


def evaluate(namespace):
    return {
        namespace_name: list(x for x in zz)
        for (namespace_name, zz) in namespace.items()
    }
