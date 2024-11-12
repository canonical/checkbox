import sys
import ast
import typing
import textwrap
import operator
import itertools
import functools
import contextlib

from copy import copy

"""
The objective of this module is to filter a namespace of resource objects
using a resource expression.

We call namespace the dict of lists that contains the output of each
resource job. Items in the lists are called objects, they are dicts where
each key is an attribute of the object and each value is a string.

Example:

    Resource job `foo` outputs:
        name: a
        value: 1

        name: b
        version: v1.2.abc
        value: 5

    Resource job `bar` outputs:
        sample_1: some
        sample_2: other

        sample_1: some
        sample_2: same

    Will generate the following namespace:

        {
            'foo' : [
                { 'name'  : 'a', 'value' : '1' },
                { 'name' : 'b', 'version' : 'v1.2.abc' }
            ],
            'bar' : [
                { 'sample_1': 'some', 'sample_2': 'other' },
                { 'sample_1': 'some', 'sample_2': 'same' }
            ]
        }

A resource expression is a function that predicates over the attributes of an
object with the objective of excluding it or including it in a query.

Example:

    "All foo having name == a"
    foo.name == 'a'

    "All foo having a value that is more than 4"
    int(foo.value) > 4

    "All foo having name a and value that is more than 4
    foo.name == 'a' and foo.value > 4
"""


class UnknownResource(KeyError): ...


class ValueGetter:
    """
    A value getter is a function that returns a value
    that is namespace independent (constant)

    Example:
        True
        [1, 2, 3]
        1.2
    """


class NamespacedGetter:
    """
    A namespaced getter is a function that returns a value
    dependent on the current namespace

    Example:
        foo.bar
        int(a.b)
    """

    def __init__(self, namespace):
        self.namespace = namespace


class CallGetter(NamespacedGetter):
    """
    This is a function call that evaluates over an attribute
    of the object. All attributes must refer to the same namespace.
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

    def __call__(self, variable_object):
        return self.function(*(arg(variable_object) for arg in self.args))

    def __str__(self):
        args = ",".join(str(x) for x in self.args)
        return "{}({})".format(self.function_name, args)


class AttributeGetter(NamespacedGetter):
    def __init__(self, parsed_ast):
        self.namespace = parsed_ast.value.id
        self.variable = parsed_ast.attr

    def __call__(self, variable_object):
        # resources are free form, support variable names not being unifrom
        try:
            return variable_object[self.variable]
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
        operand = getter_from_ast(parsed_ast.operand)
        if not isinstance(operand, ConstantGetter):
            raise ValueError(
                "`-` operator can't be applied to non-constant operands"
            )
        operand.value *= -1
        return cls(operand)

    def __str__(self):
        return str(self.value)


class NamedConstant(ConstantGetter):
    constants = {
        "DESKTOP_PC_PRODUCT": [
            "Desktop",
            "Low Profile Desktop",
            "Tower",
            "Mini Tower",
            "Space-saving",
            "All In One",
            "All-In-One",
            "AIO",
        ]
    }

    def __init__(self, parsed_ast):
        self.name = parsed_ast.id
        try:
            self.value = self.constants[self.name]
        except KeyError:
            raise NameError from KeyError

    def __str__(self):
        return "{} ({})".format(self.name, self.value)


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


legacy_getters = {}
if sys.version_info[0] == 3 and sys.version_info[1] < 8:
    from collections import namedtuple

    # older version of python have slightly different nodes to parse
    # constants. Here we wrap them for forward compatibility putting the old
    # attribute where the ConstantGetter expects to find it
    Wrapper = namedtuple("Wrapper", ["value"])

    def wrapping(attr):
        def _f(parsed_ast):
            wrapped_parsed_ast = Wrapper(getattr(parsed_ast, attr))
            return ConstantGetter(wrapped_parsed_ast)

        return _f

    legacy_getters = {
        ast.Str: wrapping("s"),
        ast.Num: wrapping("n"),
        ast.Bytes: wrapping("s"),
        # this actually uses .value
        ast.NameConstant: ConstantGetter,
    }
getters = {
    ast.Call: CallGetter,  # such as: int(group.name)
    ast.Attribute: AttributeGetter,  # such as: group.name
    ast.List: ListGetter,  # such as: [1, 2, 3]
    ast.Tuple: ListGetter,  # such as: (1, 2, 3)
    ast.UnaryOp: ConstantGetter.from_unary_op,  # such as: not True
    ast.Name: NamedConstant,  # such as: DESKTOP_PC_PRODUCT
}
getters.update(legacy_getters)
with contextlib.suppress(AttributeError):
    # new in python 3.6, all lemmas will be parsed from the legacy getters
    getters[ast.Constant] = ConstantGetter  # such as: "name"


def getter_from_ast(parsed_ast):
    """
    Rappresents a way to fetch a value
    """

    try:
        getter = getters[type(parsed_ast)]
    except KeyError:
        raise ValueError(
            "Unsupported name/value {}".format(ast.dump(parsed_ast))
        )
    return getter(parsed_ast)


class Operator:
    def __init__(self, function, text_repr):
        self.function = function
        self.text_repr = text_repr

    def __call__(self, *args, **kwargs):
        return self.function(*args, **kwargs)

    def __str__(self):
        return self.text_repr


ast_to_operator = {
    # contains(a, b) == b in a
    # so we need to swap them around
    ast.In: Operator(lambda x, y: operator.contains(y, x), "in"),
    ast.NotIn: Operator(lambda x, y: not operator.contains(x, y), "not in"),
    ast.Eq: Operator(operator.eq, "=="),
    ast.NotEq: Operator(operator.ne, "!="),
    ast.GtE: Operator(operator.ge, ">="),
    ast.LtE: Operator(operator.le, "<="),
    ast.Gt: Operator(operator.gt, ">"),
    ast.Lt: Operator(operator.lt, "<"),
}


def operator_from_ast(parsed_ast):
    try:
        return ast_to_operator[type(parsed_ast)]
    except KeyError as e:
        raise ValueError(
            "Unsupported operator {}".format(ast.dump(parsed_ast))
        ) from e


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
    def parse_from_ast(cls, parsed_ast, **kwargs):
        if len(parsed_ast.ops) != 1 or len(parsed_ast.comparators) != 1:
            raise ValueError(
                "Unsupported multi operator constrating: {}".format(
                    ast.dump(parsed_ast)
                )
            )
        left_getter = getter_from_ast(parsed_ast.left)
        right_getter = getter_from_ast(parsed_ast.comparators[0])
        return cls(left_getter, parsed_ast.ops[0], right_getter, **kwargs)

    def _filtered(self, ns_variables):

        operator_f = operator_from_ast(self.operator)

        return (
            variable_object
            for variable_object in ns_variables
            if operator_f(
                self.left_getter(variable_object),
                self.right_getter(variable_object),
            )
        )

    def filtered(self, namespaces):
        namespaces[self.namespace] = self._filtered(namespaces[self.namespace])
        return namespaces


class ConstraintExplanation:
    MORE = "[...]"

    def __init__(self, namespace_name, expression, pre_filter, post_filter):
        self.namespace_name = namespace_name
        self.expression = expression
        self.pre_filter = pre_filter
        self.post_filter = post_filter

    def __str__(self):
        return (
            textwrap.dedent(
                """
                Expression: {}
                    Pre filter:
                      {namespace_name} = {}
                    Post filter:
                      {namespace_name} = {}
                """
            )
            .strip()
            .format(
                self.expression,
                self.pre_filter,
                self.post_filter,
                namespace_name=self.namespace_name,
            )
        )


class ConstraintExplainer(Constraint):
    def __init__(self, *args, explain_callback=print, **kwargs):
        super().__init__(*args, **kwargs)
        self.explain_callback = explain_callback

    @classmethod
    def parse_from_ast(cls, parsed_ast, explain_callback):
        to_r = super().parse_from_ast(
            parsed_ast, explain_callback=explain_callback
        )
        return to_r

    def get_namespace_state(
        self, namespaces, namespace, max_namespace_items
    ) -> list:
        # we need to pretty print the namespace without destroying the
        # iterators inside it
        namespaces[namespace], printable = itertools.tee(
            namespaces[namespace], 2
        )
        # take at most max_namespace_items
        filtered_list = [
            filtered
            for i, filtered in zip(range(max_namespace_items), printable)
        ]
        try:
            # note [...] if we are truncating to max_namespace_items
            next(printable)
            filtered_list.append(ConstraintExplanation.MORE)
        except StopIteration:
            pass
        return filtered_list

    def filtered(self, namespaces, max_namespace_items=5):
        namespace = self.namespace
        expression = " ".join(
            str(x)
            for x in (
                self.left_getter,
                operator_from_ast(self.operator),
                self.right_getter,
            )
        )
        namespace_state_pre_filter = self.get_namespace_state(
            namespaces, namespace, max_namespace_items
        )

        namespaces = super().filtered(namespaces)

        namespace_state_post_filter = self.get_namespace_state(
            namespaces, namespace, max_namespace_items
        )
        self.explain_callback(
            ConstraintExplanation(
                namespace,
                expression,
                namespace_state_pre_filter,
                namespace_state_post_filter,
            )
        )

        return namespaces


def chain_uniq(*iterators):
    iterators = tuple(x for x in iterators if x)
    to_return = itertools.chain(*iterators)
    already_returned = set()
    for item in to_return:
        if item not in already_returned:
            already_returned.add(item)
            yield item


class Namespace:
    DEFAULT_NAMESPACE = "com.canonical.plainbox"

    def __init__(self, implicit_namespace, namespace):
        self.implicit_namespace = implicit_namespace
        self.namespace = namespace

    def __contains__(self, key):
        with contextlib.suppress(KeyError):
            _ = self[key]
            return True
        return False

    def __getitem__(self, key):
        """
        Namespaces keys are themselves namespaced. The priority of resolution
        is:
        1. key is in the namespace
        2. implicit_namespace::key is in the namespace
        3. DEFAULT_NAMESPACE::key is in the namespace (for example: manifest)
        """
        try:
            return self.namespace[key]
        except KeyError as e:
            with contextlib.suppress(KeyError):
                return self.namespace[
                    "{}::{}".format(self.implicit_namespace, key)
                ]
            with contextlib.suppress(KeyError):
                return self.namespace[
                    "{}::{}".format(self.DEFAULT_NAMESPACE, key)
                ]
            raise UnknownResource from e

    def __setitem__(self, key, value):
        if key in self.namespace:
            self.namespace[key] = value
            return

        implicit_namespaced_name = "{}::{}".format(
            self.implicit_namespace, key
        )
        if implicit_namespaced_name in self:
            self.namespace[implicit_namespaced_name] = value
            return

        builtin_namespaced_name = "{}::{}".format(self.DEFAULT_NAMESPACE, key)
        if builtin_namespaced_name in self:
            self.namespace[builtin_namespaced_name] = value
            return

        self.namespace[key] = value

    def items(self):
        return self.namespace.items()

    def keys(self):
        return self.namespace.keys()

    def values(self):
        return self.namespace.values()

    def get(self, key, default=None):
        with contextlib.suppress(KeyError):
            return self[key]
        return default

    def namespace_union(self, other: "Self"):
        return Namespace(
            self.implicit_namespace,
            {
                namespace_name: chain_uniq(
                    self.get(namespace_name),
                    other.get(namespace_name),
                )
                for namespace_name in (self.keys() | other.keys())
            },
        )

    def duplicate_namespace(self, count: int):
        duplicated_namespace = {
            x: itertools.tee(y, count) for (x, y) in self.items()
        }
        namespaces = [
            Namespace(
                self.implicit_namespace,
                {
                    key: duplicated_namespace[key][i]
                    for key in duplicated_namespace
                },
            )
            for i in range(count)
        ]
        return namespaces


namespace_union = Namespace.namespace_union


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
        duplicated_namespaces = namespace.duplicate_namespace(
            len(bool_op.values)
        )
        ns_constraint = zip(duplicated_namespaces, bool_op.values)
        filtered_namespaces = (
            _prepare_filter(constraint, namespace, constraint_class)
            for namespace, constraint in ns_constraint
        )
        return functools.reduce(Namespace.namespace_union, filtered_namespaces)
    raise ValueError("Unsupported boolean operator: {}".format(bool_op.op))


@_prepare_filter.register(ast.Expression)
def _prepare_expression(ast_item, namespace, constraint_class):
    return _prepare_filter(ast_item.body, namespace, constraint_class)


@_prepare_filter.register(ast.Compare)
def _prepare_compare(ast_item, namespace, constraint_class):
    return constraint_class(ast_item).filtered(namespace)


def prepare(
    expr: typing.Union[ast.AST, str],
    namespace: dict,
    implicit_namespace: str = "",
    explain_callback=None,
):
    """
    This function returns a namespace with the same keys and values that are
    iterators that returns only the values that were in the original namespace
    that match the parsed expression.

    Ex.
    input_namespace = { 'a' : [{'v' : 1}, {'v' : 2}] }
    parsed_expr ~= 'a.v > 1'
    output_namespace = {'a' : (x for x in input_namespace['a'] if x['v'] > 1) }

    When explain_callback is provided, each filtering action done will call
    the callback with a ConstraintExplanation object

    Ex.
    Expression: namespace.a In() [1, 2]
      Pre filter:
        {'a': '1'}
        {'a': '2'}
        {'a': '3'}
        [...]
      Post filter:
        {'a': '1'}
        {'a': '2'}
    """
    if explain_callback:
        CC = functools.partial(
            ConstraintExplainer.parse_from_ast,
            explain_callback=explain_callback,
        )
    else:
        CC = Constraint.parse_from_ast
    if isinstance(expr, str):
        expr = ast.parse(expr, mode="eval")
    return _prepare_filter(
        expr, Namespace(implicit_namespace, copy(namespace)), CC
    )


def evaluate_lazy(
    expr: typing.Union[ast.AST, str],
    namespace: dict,
    implicit_namespace: str = "",
    explain_callback=None,
) -> bool:
    """
    This returns a new namespaces where each id has a truth value given
    a resource expression

    Returns a namespace where each value is True if any object matched the
    expression. This is used when one doesn't need to know which objects match
    the expression but whether something actually does, namely, when
    deciding if a job with `resource:...` has to run or not.

    To get a True/False answer one can simply use:
        all(evaluate_lazy(...).values())
    """
    namespace = prepare(
        expr,
        namespace,
        implicit_namespace=implicit_namespace,
        explain_callback=explain_callback,
    )

    def any_next(iterable):
        try:
            next(iterable)
            return True
        except StopIteration:
            return False

    return {x: any_next(iter(v)) for (x, v) in namespace.items()}


def evaluate(
    expr: typing.Union[ast.AST, str],
    namespace: dict,
    implicit_namespace: str = "",
    explain_callback=None,
):
    """
    This returns a filtered namespace where each id has only the keys that
    match a given resource expression
    """
    namespace = prepare(
        expr,
        namespace,
        implicit_namespace=implicit_namespace,
        explain_callback=explain_callback,
    )
    return {
        namespace_name: list(values_iterator)
        for (namespace_name, values_iterator) in namespace.items()
    }
