import ast
import operator
import itertools
import functools

from copy import copy


class ValueGetter:
    """
    A value getter is a function that returns a value
    that is independent from variables in any namespace
    """


class NamespacedGetter:
    """
    A namespaced getter is a function that returns a value
    dependent on the current namespace
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
                        "Function call can access at most one namespace "
                        "({} != {})".format(namespace, arg_ns)
                    )
                namespace = arg_ns
            except AttributeError:
                pass
        if namespace is None:
            raise ValueError(
                "Function calls with no namespace are unsupported"
            )
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
        return "{}({})".format(self.function_name, args)


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
        return "{}.{}".format(self.namespace, self.variable)


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
        return str(self.value)


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
    """
    Rappresents a way to get a value
    """
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


class Constraint:
    """
    Rappresents a filter to be applied on a namespace
    """

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


class ConstraintExplainer(Constraint):
    def pretty_print(self, namespaces, namespace, max_namespace_items):
        namespaces[namespace] = list(namespaces[namespace])
        for filtered in namespaces[namespace][:max_namespace_items]:
            print("   ", filtered)
        if len(namespaces[namespace]) > max_namespace_items:
            print("    [...]")

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
        self.pretty_print(namespaces, namespace, max_namespace_items)

        namespaces = super().filtered(namespaces)

        print("  Post filter: ")
        self.pretty_print(namespaces, namespace, max_namespace_items)

        return namespaces


def dct_hash(dict_obj):
    return hash(frozenset(dict_obj.items()))


def chain_uniq(*iterators):
    to_return = itertools.chain(*iterators)
    already_returned = set()
    for item in to_return:
        h_item = dct_hash(item)
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


@functools.singledispatch
def _prepare_filter(ast_item: ast.AST, namespace, constraint_class):
    """
    This function edits the namespace in place replacing each value
    with an iterator that returns only the values that were in the original
    namespace that match the parsed expression.

    Warning: This edits the input namespace in place

    Ex.
    input_namespace = { 'a' : [{'v' : 1}, {'v' : 2}] }
    parsed_expr ~= 'a.v > 1'
    output_namespace = {'a' : (x for x in input_namespace['a'] if x['v'] > 1) }
    """
    raise NotImplementedError(
        "Unsupported ast item: {}".format(ast.dump(ast_item))
    )


@_prepare_filter.register(ast.BoolOp)
def _prepare_boolop(bool_op, namespace, constraint_class):
    if isinstance(bool_op.op, ast.And):
        return functools.reduce(
            lambda ns, constraint: _prepare_filter(
                constraint, ns, constraint_class
            ),
            bool_op.values,
            namespace,
        )
    elif isinstance(bool_op.op, ast.Or):
        duplicated_namespaces = duplicate_namespace(
            namespace, len(bool_op.values)
        )
        ns_constraint = zip(duplicated_namespaces, bool_op.values)
        filtered_namespaces = (
            _prepare_filter(constraint, namespace, constraint_class)
            for namespace, constraint in ns_constraint
        )
        return functools.reduce(namespace_union, filtered_namespaces)
    raise ValueError("Unsupported boolean operator: {}".format(bool_op.op))


@_prepare_filter.register(ast.Expression)
def _prepare_expression(ast_item, namespace, constraint_class):
    return _prepare_filter(ast_item.body, namespace, constraint_class)


@_prepare_filter.register(ast.Compare)
def _prepare_compare(ast_item, namespace, constraint_class):
    return constraint_class.parse_from_ast(ast_item).filtered(namespace)


def prepare(parsed_expr: ast.AST, namespace, explain=False):
    """
    This function returns a namespace with the same keys and values that are
    iterators that returns only the values that were in the original namespace
    that match the parsed expression.

    Ex.
    input_namespace = { 'a' : [{'v' : 1}, {'v' : 2}] }
    parsed_expr ~= 'a.v > 1'
    output_namespace = {'a' : (x for x in input_namespace['a'] if x['v'] > 1) }
    """
    if explain:
        CC = ConstraintExplainer
    else:
        CC = Constraint
    return _prepare_filter(parsed_expr, copy(namespace), CC)


def parse_prepare(expr: str, namespace, explain=False):
    if explain:
        CC = Constraint
    else:
        CC = ConstraintExplainer
    parsed_expr = ast.parse(expr, mode="eval")
    # print(ast.dump(parsed_expr))
    return _prepare_filter(parsed_expr, copy(namespace), CC)


def evaluate_lazy(namespace) -> bool:
    """
    This returns the truth value of a prepared namespace.
    Returns True if all values iterator contain at least one item
    """

    def any_next(iterable):
        try:
            next(iterable)
            return True
        except StopIteration:
            return False

    return all(any_next(iter(v)) for v in namespace.values())


def evaluate(namespace):
    return {
        namespace_name: list(values_iterator)
        for (namespace_name, values_iterator) in namespace.items()
    }
