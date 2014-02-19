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
:mod:`plainbox.impl.resource` -- job resources
==============================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import ast
import logging

from plainbox.i18n import gettext as _

logger = logging.getLogger("plainbox.resource")


class ExpressionFailedError(Exception):
    """
    Exception raise when a resource expression failed to produce a true value.

    This class is meant to be consumed by the UI layers to provide meaningful
    error messages to the operator. The expression attribute can be used to
    obtain the text of the expression that failed as well as the resource id
    that is used by that expression. The resource id can be used to lookup
    the (resource) job that produces such values.
    """

    def __init__(self, expression):
        self.expression = expression

    def __str__(self):
        return _("expression {!r} evaluated to a non-true result").format(
            self.expression.text)

    def __repr__(self):
        return "<{} expression:{!r}>".format(
            self.__class__.__name__, self.expression)


class ExpressionCannotEvaluateError(ExpressionFailedError):
    """
    Exception raised when a resource could not be evaluated because it requires
    an unavailable resource.

    Unlike the base class, this exception is raised before even running the
    expression. As in the base class the exception object is meant to have
    enough data to provide rich and meaningful error messages to the operator.
    """

    def __str__(self):
        return _("expression {!r} needs unavailable resource {!r}").format(
            self.expression.text, self.expression.resource_id)


class Resource:
    """
    A simple container for key-value data

    Resource objects are used when evaluating expressions as containers for
    data read from resource scripts. Each RFC822 record produced by a resource
    script is converted to a new Resource object
    """

    __slots__ = ('_data')

    def __init__(self, data=None):
        if data is None:
            data = {}
        object.__setattr__(self, '_data', data)

    def __setattr__(self, attr, value):
        if attr.startswith("_"):
            raise AttributeError(attr)
        data = object.__getattribute__(self, '_data')
        data[attr] = value

    def __delattr__(self, attr):
        data = object.__getattribute__(self, '_data')
        if attr in data:
            del data[attr]
        else:
            raise AttributeError(attr)

    def __getattribute__(self, attr):
        if attr.startswith("_"):
            raise AttributeError(attr)
        data = object.__getattribute__(self, '_data')
        if attr in data:
            return data[attr]
        else:
            raise AttributeError(attr)

    def __repr__(self):
        data = object.__getattribute__(self, '_data')
        return "Resource({!r})".format(data)

    def __eq__(self, other):
        if not isinstance(other, Resource):
            return False
        return (
            object.__getattribute__(self, '_data')
            == object.__getattribute__(other, '_data'))

    def __ne__(self, other):
        if not isinstance(other, Resource):
            return True
        return (
            object.__getattribute__(self, '_data')
            != object.__getattribute__(other, '_data'))


class ResourceProgram:
    """
    Class for storing and executing resource programs.

    This is used by job requirement expressions
    """

    def __init__(self, program_text):
        """
        Analyze the requirement program and prepare it for execution

        The requirement program must be a string (of possibly many lines), each
        of which must be a valid ResourceExpression. Empty lines are ignored.

        May raise ResourceProgramError (including CodeNotAllowed) or a
        SyntaxError
        """
        self._expression_list = []
        for line in program_text.splitlines():
            if line.strip() != "":
                self._expression_list.append(ResourceExpression(line))

    @property
    def expression_list(self):
        """
        A list of ResourceExpression instances
        """
        return self._expression_list

    @property
    def required_resources(self):
        """
        A set() of resource ids that are needed to evaluate this program
        """
        return set((expression.resource_id
                    for expression in self._expression_list))

    def evaluate_or_raise(self, resource_map):
        """
        Evaluate the program with the given map of resources.

        Raises a ExpressionFailedError exception if the any of the expressions
        that make up this program cannot be executed or executes but produces a
        non-true value.

        Returns True

        Resources must be a dictionary of mapping resource id to a list of
        Resource objects.
        """
        # First check if we have all required resources
        for expression in self._expression_list:
            if expression.resource_id not in resource_map:
                raise ExpressionCannotEvaluateError(expression)
        # Then evaluate all expressions
        for expression in self._expression_list:
            result = expression.evaluate(
                resource_map[expression.resource_id])
            if not result:
                raise ExpressionFailedError(expression)
        return True


class ResourceProgramError(Exception):
    """
    Base class for errors in requirement programs.

    This class of errors are based on static analysis, not runtime execution.
    Typically they encode unsupported or disallowed python code being used by
    an expression somewhere.
    """


class CodeNotAllowed(ResourceProgramError):
    """
    Exception raised when unsupported computing is detected inside requirement
    expression.
    """

    def __init__(self, node):
        self.node = node

    def __repr__(self):
        return "CodeNotAllowed({!r})".format(self.node)

    def __str__(self):
        return _("this kind of python code is not allowed: {}").format(
            ast.dump(self.node))


class ResourceNodeVisitor(ast.NodeVisitor):
    """
    A NodeVisitor subclass used to analyze requirement expressions.

    .. warning::

        Implementation of this class requires understanding of
        some of the lower levels of python. The general idea is
        to use the ast (abstract syntax tree) module to allow
        the ResourceExpression class to execute safely (by
        not permitting various unsafe operations) and quickly
        (by knowing which resources are required so no O(n)
        operations over all resources are ever needed.

    Resource expressions are written one per line, each line is like a
    separate min-program. This visitor will be applied to the root (module)
    node resulting from parsing each of those lines.

    Each actual expression can only use a small subset of python syntax, most
    stuff is actually disallowed. Only basic expressions are permitted.
    Function calls are also disallowed, with the notable exception of 'bool',
    'int', 'float' and 'len'.

    One very important aspect of each expression is the id of the resource it
    is computing against. This is visible as the 'object' the expressions are
    operating on, such as:

        package.name == 'fwts'

    As a rule of a thumb exactly one such id is allowed per expression. This
    allows the code that evaluates this to know which resource to use. As
    resources are actually lists of records (where record values are available
    as object attribute) only one object/record is exposed to each expression.
    Using more than one object (by intent or simple typo) would lead to
    expression that will never match. This visitor class facilitates detecting
    that by computing the ids_seen set.

    One notable fact is that storing is not allowed so it is (presumably) safe
    to evaluate the code in the context of the current python interpreter.

    How this works:

    Using the ast.NodeVisitor we can visit any node type by defining the
    visit_<class name> method. We care about Name and Call nodes and they have
    custom validation implemented. For all other nodes the generic_visit()
    method is called instead.

    On each visit to ast.Name node we record the referenced 'id' (the id of
    the object being referenced, in simple terms)

    On each visit to ast.Call node we check if the called function is in the
    allowed list of ids. This also takes care of stuff like foo()() which
    would call the return value of foo.

    On each visit to any other ast.Node we check if the class is in the
    white-list.

    All violation cause a CodeNotAllowed exception to be raised with the
    node that was rejected as argument.
    """

    # Allowed function calls
    _allowed_call_func_list = (
        'len',
        'bool',
        'int',
        'float',
    )

    # A tuple of allowed types of ast.Node that are white-listed by
    # _check_node()
    _allowed_node_cls_list = (
        # Allowed statements (ast.stmt sub-classes)
        ast.Expr,  # expressions

        # Allowed 'mod's (ast.mod sub-classes)
        ast.Module,

        # Allowed expressions (ast.expr sub-classes)
        ast.Attribute,  # attribute access
        ast.BinOp,  # binary operators
        ast.BoolOp,  # boolean operations (and/or)
        ast.Compare,  # comparisons
        ast.List,  # lists
        ast.Name,  # name access (top-level name references)
        ast.Num,  # numbers
        ast.Str,  # strings
        ast.Tuple,  # tuples
        ast.UnaryOp,  # unary operators

        # Allow all comparison operators
        ast.cmpop,  # this allows ast.Eq, ast.Gt and so on

        # Allow all boolean operators
        ast.boolop,  # this allows ast.And, ast.Or

        # Allowed expression context (ast.expr_context)
        ast.Load,  # allow all loads
    )

    def __init__(self):
        """
        Initialize a ResourceNodeVisitor with empty set of ids_seen
        """
        self._ids_seen = set()

    @property
    def ids_seen(self):
        """
        set() of ast.Name().id values seen
        """
        return self._ids_seen

    def visit_Name(self, node):
        """
        Internal method of NodeVisitor.

        This method is called whenever generic_visit() looks at an instance of
        ast.Name(). It records the node identifier and calls _check_node()
        """
        self._check_node(node)
        self._ids_seen.add(node.id)

    def visit_Call(self, node):
        """
        Internal method of NodeVisitor.

        This method is called whenever generic_visit() looks at an instance of
        ast.Call(). Since white-listing Call in general would be unsafe only a
        small subset of calls are allowed.
        """
        # XXX: Do not call _check_node() here as Call is not on the whitelist
        if node.func.id not in self._allowed_call_func_list:
            raise CodeNotAllowed(node)

    def generic_visit(self, node):
        """
        Internal method of NodeVisitor.

        Called for all ast.Node() subclasses that don't have a dedicated
        visit_xxx() method here. Only needed to all the _check_node() method.
        """
        self._check_node(node)
        return super(ResourceNodeVisitor, self).generic_visit(node)

    def _check_node(self, node):
        """
        Internal method of ResourceNodeVisitor.

        This method raises CodeNotAllowed() for any node that is outside
        of the set of supported node classes.
        """
        if not isinstance(node, self._allowed_node_cls_list):
            raise CodeNotAllowed(node)


class RequirementNodeVisitor(ast.NodeVisitor):
    """
    A NodeVisitor subclass used to analyze package requirement expressions.
    """

    def __init__(self):
        """
        Initialize a ResourceNodeVisitor with empty list of packages_seen
        """
        self._packages_seen = []

    @property
    def packages_seen(self):
        """
        set() of ast.Str().id values seen joined with the "|" operator for
        use in debian/control files
        """
        return self._packages_seen

    def visit_Str(self, node):
        """
        Internal method of NodeVisitor.

        This method is called whenever generic_visit() looks at an instance of
        ast.Str().
        """
        self._packages_seen.append(node.s)


class NoResourcesReferenced(ResourceProgramError):
    """
    Exception raised when an expression does not reference any resources.
    """

    def __str__(self):
        return _("expression did not reference any resources")


class MultipleResourcesReferenced(ResourceProgramError):
    """
    Exception raised when an expression references multiple resources.
    """

    def __str__(self):
        return _("expression referenced multiple resources")


class ResourceExpression:
    """
    Class representing a single line of an requirement program.

    Each valid expression references exactly one resource. In practical terms
    each resource expression is a valid python expression that has no side
    effects (calls almost no methods, does not assign anything) that can be
    evaluated against a single variable which references a Resource object.
    """

    def __init__(self, text):
        """
        Analyze the text and prepare it for execution

        May raise ResourceProgramError
        """
        self._resource_id = self._analyze(text)
        self._text = text
        self._lambda = eval("lambda {}: {}".format(
            self._resource_id, self._text))

    def __str__(self):
        return self._text

    def __repr__(self):
        return "<ResourceExpression text:{!r}>".format(self._text)

    def __eq__(self, other):
        if isinstance(other, ResourceExpression):
            return self._text == other._text
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, ResourceExpression):
            return self._text != other._text
        return NotImplemented

    @property
    def text(self):
        """
        The text of the original expression
        """
        return self._text

    @property
    def resource_id(self):
        """
        The id of the resource this expression depends on
        """
        return self._resource_id

    def evaluate(self, resource_list):
        """
        Evaluate the expression against a list of resources

        Each subsequent resource from the list will be bound to the resource
        id in the expression. The return value is True if any of the attempts
        return a true value, otherwise the result is False.
        """
        # Try each resource in sequence.
        for resource in resource_list:
            if not isinstance(resource, Resource):
                raise TypeError("Each resource must be a Resource instance")
            # Attempt to evaluate the code with the current resource
            try:
                result = self._lambda(resource)
            except Exception as exc:
                # Treat any exception as a non-fatal error
                #
                # XXX: it would be interesting to see if we have exceptions and
                # why they happen.  We could do deeper validation this way.
                logger.debug(
                    _("Exception in requirement expression %r (with %s=%r):"
                      " %r"), self._text, self._resource_id, resource, exc)
                continue
            # Treat any true result as a success
            if result:
                return True
        # If we get here then the expression did not match. It's pointless (as
        # python returns None implicitly) but it's more explicit on the
        # documentation side.
        return False

    @classmethod
    def _analyze(cls, text):
        """
        Analyze the expression and return the id of the required resource

        May raise SyntaxError or a ResourceProgramError subclass
        """
        # Use the ast module to build an abstract syntax tree of the expression
        node = ast.parse(text)
        # Use ResourceNodeVisitor to see what kind of ast.Name objects are
        # referenced by the expression. This may also raise CodeNotAllowed
        # which should be captured by the higher layers.
        visitor = ResourceNodeVisitor()
        visitor.visit(node)
        # Bail if the expression is not using exactly one resource id
        if len(visitor.ids_seen) == 0:
            raise NoResourcesReferenced()
        elif len(visitor.ids_seen) == 1:
            return list(visitor.ids_seen)[0]
        else:
            raise MultipleResourcesReferenced()
