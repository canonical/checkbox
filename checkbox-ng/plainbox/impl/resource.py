# This file is part of Checkbox.
#
# Copyright 2012-2020 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
import itertools
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

    def __init__(self, expression, resource_id):
        self.expression = expression
        self.resource_id = resource_id

    def __str__(self):
        return _("expression {!r} needs unavailable resource {!r}").format(
            self.expression.text, self.resource_id)


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

    def __iter__(self):
        data = object.__getattribute__(self, '_data')
        return iter(data)

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

    def __getattr__(self, attr):
        data = object.__getattribute__(self, '_data')
        if attr in data:
            return data[attr]
        else:
            return ''

    def __getattribute__(self, attr):
        if attr != "_data":
            return object.__getattribute__(self, attr)
        else:
            raise AttributeError("don't poke at _data")

    def __getitem__(self, item):
        data = object.__getattribute__(self, '_data')
        return data[item]

    def __setitem__(self, item, value):
        data = object.__getattribute__(self, '_data')
        data[item] = value

    def __delitem__(self, item):
        data = object.__getattribute__(self, '_data')
        del data[item]

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


class FakeResource:
    """
    A resource that seemingly has any accessed attribute.

    All attributes resolve back to their names. All accessed attributes are
    recorded and can be referenced from a set that needs to be passed to the
    initializer. Knowledge about accessed attributes can be helpful in various
    forms of static analysis.
    """

    def __init__(self, accessed_attributes=None):
        """
        Initialize a fake resource object.

        :param accessed_attributes:
            An optional set object that will record all accessed resource
            attributes.
        """
        self._accessed_attributes = accessed_attributes

    def _notice(self, attr):
        if self._accessed_attributes is not None:
            self._accessed_attributes.add(attr)

    def __getattr__(self, attr):
        self._notice(attr)
        return attr

    def __getitem__(self, item):
        self._notice(item)
        return item

    def __contains__(self, item):
        return True


class ResourceProgram:
    """
    Class for storing and executing resource programs.

    This is used by job requirement expressions
    """

    def __init__(self, program_text, implicit_namespace=None, imports=None):
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
                self._expression_list.append(
                    ResourceExpression(line, implicit_namespace, imports))

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
        ids = set()
        for expression in self._expression_list:
            for resource_id in expression.resource_id_list:
                ids.add(resource_id)
        return ids

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
            for resource_id in expression.resource_id_list:
                if resource_id not in resource_map:
                    raise ExpressionCannotEvaluateError(
                        expression, resource_id)
        # Then evaluate all expressions
        for expression in self._expression_list:
            result = expression.evaluate(*[
                resource_map[resource_id]
                for resource_id in expression.resource_id_list
            ], resource_map = resource_map)
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
        Initialize a ResourceNodeVisitor with empty trace of seen identifiers
        """
        self._ids_seen_set = set()
        self._ids_seen_list = []
        self._manifest_attr_seen_list = []

    @property
    def ids_seen_set(self):
        """
        set() of ast.Name().id values seen
        """
        return self._ids_seen_set

    @property
    def ids_seen_list(self):
        """
        list() of ast.Name().id values seen
        """
        return self._ids_seen_list

    @property
    def manifest_attr_seen_list(self):
        """
        list() of ast.Attribute().attr values seen
        """
        return self._manifest_attr_seen_list

    def visit_Name(self, node):
        """
        Internal method of NodeVisitor.

        This method is called whenever generic_visit() looks at an instance of
        ast.Name(). It records the node identifier and calls _check_node()
        """
        self._check_node(node)
        if node.id not in self._ids_seen_set:
            self._ids_seen_set.add(node.id)
            self._ids_seen_list.append(node.id)

    def visit_Attribute(self, node):
        """
        Internal method of NodeVisitor.

        This method is called whenever generic_visit() looks at an instance of
        ast.Attribute(). It records the attr identifier
        """
        self._check_node(node)
        if isinstance(node.value, ast.Name):
            self.visit_Name(node.value)
            if node.value.id == 'manifest':
                if node.attr not in self._manifest_attr_seen_list:
                    self._manifest_attr_seen_list.append(node.attr)

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


class ResourceSyntaxError(ResourceProgramError):

    def __str__(self):
        return _("syntax error in resource expression")


class ResourceExpression:
    """
    Class representing a single line of an requirement program.

    Each valid expression references exactly one resource. In practical terms
    each resource expression is a valid python expression that has no side
    effects (calls almost no methods, does not assign anything) that can be
    evaluated against a single variable which references a Resource object.
    """

    def __init__(self, text, implicit_namespace=None, imports=None):
        """
        Analyze the text and prepare it for execution

        May raise ResourceProgramError
        """
        self._implicit_namespace = implicit_namespace
        self._resource_alias_list = self._analyze(text)
        self._manifest_id_list = self._analyze_manifest(text)
        self._resource_id_list = []
        self._imports = imports
        if imports is None:
            imports = ()
        # Respect any import statements.
        # They always take priority over anything we may know locally
        for resource_alias in self._resource_alias_list:
            for imported_resource_id, imported_alias in imports:
                if imported_alias == resource_alias:
                    self._resource_id_list.append(imported_resource_id)
                    break
            else:
                self._resource_id_list.append(resource_alias)
        self._text = text
        self._lambda = eval("lambda {}: {}".format(
            ', '.join(self._resource_alias_list), self._text))

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
    def resource_id_list(self):
        """
        The id of the resource this expression depends on

        This is different from :meth:`resource_alias` in that it may not be a
        valid python identifier and it is always (ideally) a fully-qualified
        job identifier.
        """
        return [
            "{}::{}".format(self._implicit_namespace, resource_id)
            if "::" not in resource_id and self._implicit_namespace
            else resource_id
            for resource_id in self._resource_id_list
        ]

    @property
    def manifest_id_list(self):
        return self._manifest_id_list

    @property
    def resource_alias_list(self):
        """
        The alias of the resource object this expression operates on

        This is different from :meth:`resource_id` in that it is always a valid
        python identifier. The alias is either the partial identifier of the
        resource job or an arbitrary identifier, as used by the job definition.
        """
        return self._resource_alias_list

    @property
    def implicit_namespace(self):
        """
        implicit namespace for partial identifiers, may be None
        """
        return self._implicit_namespace

    def evaluate(self, *resource_list_list, resource_map=None):
        """
        Evaluate the expression against a list of resources

        Each subsequent resource from the list will be bound to the resource
        id in the expression. The return value is True if any of the attempts
        return a true value, otherwise the result is False.
        """
        # in compound expressions 'and' takes precedence over 'or' so because
        # we're recursively evaluating, we need to first evaluate the ors so
        # ands become the leaves in the tree and are actually computed first

        # operator by itself may be a part of some identifier so let's
        # look for one surrounded by spaced

        # if parenthesis are used in the expression then there's a high chance
        # we'll break the syntax with a bruteforce split on operator. Let's
        # not do a split on exprs with parenthesis
        if not '(' in self._text:
            or_pos = self._text.rfind(' or ')
            if or_pos > 0:
                lhs, rhs = self._split_and_evaluate(' or ', resource_map)
                return lhs or rhs
            and_pos = self._text.rfind(' and ')
            if and_pos > 0:
                lhs, rhs = self._split_and_evaluate(' and ', resource_map)
                return lhs and rhs

        # there are no conjuctions, so let's do a simple evaluation
        for resource_list in resource_list_list:
            for resource in resource_list:
                if not isinstance(resource, Resource):
                    raise TypeError(
                        "Each resource must be a Resource instance")
        # Try each resource in sequence.
        for resource_pack in itertools.product(*resource_list_list):
            # Attempt to evaluate the code with the current resource
            try:
                result = self._lambda(*resource_pack)
            except Exception as exc:
                # Treat any exception as a non-fatal error
                #
                # XXX: it would be interesting to see if we have exceptions and
                # why they happen.  We could do deeper validation this way.
                logger.debug(
                    _("Exception in requirement expression %r (with %s=%r):"
                      " %r"),
                    self._text, self._resource_id_list, resource, exc)
                continue
            # Treat any true result as a success
            if result:
                return True
        # If we get here then the expression did not match. It's pointless (as
        # python returns None implicitly) but it's more explicit on the
        # documentation side.
        return False

    def _split_and_evaluate(self, operator, resource_map):
        head, tail = self._text.rsplit(operator, 1)
        head_expr = ResourceExpression(
            head, self._implicit_namespace, self._imports)
        new_res_list = [
            resource_map[rid] for rid in head_expr.resource_id_list]
        head_result = head_expr.evaluate(
            *new_res_list, resource_map = resource_map)
        tail = tail.strip()
        tail_expr = ResourceExpression(
            tail, self._implicit_namespace, self._imports)
        new_res_list = [
            resource_map[rid] for rid in tail_expr.resource_id_list]
        tail_result = tail_expr.evaluate(
            *new_res_list, resource_map = resource_map)
        return (head_result, tail_result)


    @classmethod
    def _analyze(cls, text):
        """
        Analyze the expression and return the id of the required resource

        May raise SyntaxError or a ResourceProgramError subclass
        """
        # Use the ast module to build an abstract syntax tree of the expression
        try:
            node = ast.parse(text)
        except SyntaxError:
            raise ResourceSyntaxError
        # Use ResourceNodeVisitor to see what kind of ast.Name objects are
        # referenced by the expression. This may also raise CodeNotAllowed
        # which should be captured by the higher layers.
        visitor = ResourceNodeVisitor()
        visitor.visit(node)
        # Bail if the expression is not using exactly one resource id
        if len(visitor.ids_seen_list) == 0:
            raise NoResourcesReferenced()
        else:
            return list(visitor.ids_seen_list)

    def _analyze_manifest(self, text):
        """
        Analyze the expression and return the id of the manifest resource

        May raise SyntaxError or a ResourceProgramError subclass
        """
        # Use the ast module to build an abstract syntax tree of the expression
        try:
            node = ast.parse(text)
        except SyntaxError:
            raise ResourceSyntaxError
        # Use ResourceNodeVisitor to see what kind of ast.Name objects are
        # referenced by the expression. This may also raise CodeNotAllowed
        # which should be captured by the higher layers.
        visitor = ResourceNodeVisitor()
        visitor.visit(node)
        # Bail if the expression is not using exactly one resource id
        if len(visitor.ids_seen_list) == 0:
            raise NoResourcesReferenced()
        else:
            return [
                "{}::{}".format(self._implicit_namespace, manifest_id)
                if "::" not in manifest_id and self._implicit_namespace
                else manifest_id
                for manifest_id in list(visitor.manifest_attr_seen_list)
            ]


def parse_imports_stmt(imports):
    """
    Parse the 'imports' line and compute the imported symbols.

    Return generator for a sequence of pairs (job_id, identifier) that
    describe the imported job identifiers from arbitrary namespace.

    The syntax of each imports line is:

    IMPORT_STMT ::  "from" <NAMESPACE> "import" <PARTIAL_ID>
                  | "from" <NAMESPACE> "import" <PARTIAL_ID>
                     AS <IDENTIFIER>
    """
    # Poor man's parser. Replace this with our own parser once we get one
    for lineno, line in enumerate(imports.splitlines()):
        parts = line.split()
        if len(parts) not in (4, 6):
            raise ValueError(
                _("unable to parse imports statement {0!r}: expected"
                  " exactly four or six tokens").format(line))
        if parts[0] != "from":
            raise ValueError(
                _("unable to parse imports statement {0!r}: expected"
                  " 'from' keyword").format(line))
        namespace = parts[1]
        if "::" in namespace:
            raise ValueError(
                _("unable to parse imports statement {0!r}: expected"
                  " a namespace, not fully qualified job identifier"))
        if parts[2] != "import":
            raise ValueError(
                _("unable to parse imports statement {0!r}: expected"
                  " 'import' keyword").format(line))
        job_id = effective_id = parts[3]
        if "::" in job_id:
            raise ValueError(
                _("unable to parse imports statement {0!r}: expected"
                  " a partial job identifier, not a fully qualified job"
                  " identifier").format(line))
        if len(parts) == 6:
            if parts[4] != "as":
                raise ValueError(
                    _("unable to parse imports statement {0!r}: expected"
                      " 'as' keyword").format(line))
            effective_id = parts[5]
        yield ("{}::{}".format(namespace, job_id), effective_id)
