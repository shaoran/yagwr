"""
This module implements a simple checker that checks whether a condition
matches in a dictionary. It is similar to
`JsonLogic <https://jsonlogic.com/>`_ but it is also much more simpler
because it's not a general solution and only matches dictionaries
whose keys and values are strings only.

With this module you can solve *Is the value of key A equals 5
and does this regex match the value of key B?*-kind of questions.

The conditions can be built directly by generating :py:class:`Node` objects
and linking them toghether according to your logic rules, or you can
create a dictionary and parse it with :py:func:`parse_from_object`.

.. _condition dictionary:

The condition dictionary
~~~~~~~~~~~~~~~~~~~~~~~~


You have three basic operators: **ANY** (corresponds to boolean ``OR``),
**ALL** (corresponds to boolean ``AND``) and **NOT** (corresponds to boolean ``NOT``).

The basic grammer rules are::

    <node> ::= <terminal-node> | <OP>([<node>, <node>, ...])

    <terminal-node> ::= "key = value" | "key != value" | "key ~= regex" | "key !~= regex"

    <OP> ::= "ANY" | "ALL" | "NOT"


The ``<OP>`` (operator) corresponds to the dictionary key. The operands (the other ``<node>``\s)
are decoded inside a list. That means that you always need at least one operator.

Example
~~~~~~~

We want to implement this condition::

    (akane != kun) OR ( (genma = san) AND (nabiki ~= tendou?) )

The dictionary with this rules is:

.. code-block:: python

    {
        "ANY": [
            "akane != kun",
            {
                "ALL": [
                    "genma = san",
                    "nabiki ~= tendou?"
                ]
            }
        ]
    }

The following dictionary will match the condition:

.. code-block:: python

    {
        "akane": "chan",
        "ranma": "kun",
        "genma": "san",
        "nabiki": "tendo",
    }

The following dictionary will **not** match the condition:

.. code-block:: python

    {
        "akane": "chan",
        "ranma": "kun",
        "genma": "saotome",
        "nabiki": "tendo",
    }

.. note::

    For simplicity, the left-hand-side of ``<terminal-node>`` string
    supports letters, numbers, dashes and underscores only. The module uses
    the following regular expression ``\w[\w\s]*`` to match the left-hand-side.

    Adding full unicode support would make the code unnecessarily complicated, specially
    since in ``yagwr`` the dictionaries to be matched are going to contains
    those characters only.

    If you need something more powerful or a more general solution,
    we recommend `JsonLogic <https://jsonlogic.com/>`_.
"""

import re


class InvalidExpression(Exception):
    """
    This exception is raised when parsing the condition-dictionary fails
    because of an incorrect type was passed.
    """

    pass


class Node:
    """
    The base node. All nodes must have at least one children.

    Do not instantiate this class directly.
    """

    def __init__(self, kind, children=[]):
        """
        :param str kind: A string representation of the kind of the node
        :param list children: a list of the children of the node,
            they must be of type :py:class:`Node`.
        """
        self.kind = kind
        self.children = children

    def eval(self, ref):
        """
        Evaluates the condition in the node given a dictionary

        :param dict ref: the dictionary to be evaluated
        :returns bool: ``True`` if the condition matches the values
            in the dictionary, ``False`` otherwise.
        """
        raise NotImplemented("Evaluation not implemented")

    def __repr__(self):
        m = [repr(x) for x in self.children]
        return f"<{self.kind}: [{', '.join(m)}]>"

    def to_dict(self):
        """
        :return: The condition in dictionary form.
        :rtype: dict
        """
        if isinstance(self, LiteralNode):
            return self.children[0]

        if isinstance(self, (NotNode, AnyNode, AllNode)):
            children = [n.to_dict() for n in self.children]

            return {self.kind.lower(): children}


class LiteralNode(Node):
    """
    A *Literal Node*, that means it's a terminal node. It doesn't have children.
    """

    def __init__(self, expr):
        """
        :param str expr: the boolean expression. The operator can be one of: ``=`` (equals),
            ``!=`` (not equals), ``~=`` matches regular expression, ``!~=`` doesn not match regular expression.
            The left-hand-side and the right-hand-side values are trimmed.
        """
        if not isinstance(expr, str):
            raise InvalidExpression(f"{expr!r} must be a string")

        m = re.match(r"(?P<LHS>\w[\w\s]*)(?P<OP>=|!=|~=|!~=)(?P<RHS>.*)$", expr)

        if not m:
            raise InvalidExpression(f"{expr!r} is not a valud key<OP>val expression")

        super().__init__("Literal", [expr])

        self.tokens = m.groupdict()

    def eval(self, ref):
        try:
            value = ref[self.tokens["LHS"].strip()]
        except KeyError:
            return False

        op = self.tokens["OP"]

        eqs = self.tokens["RHS"].strip() == value.strip()
        reg = bool(re.match(self.tokens["RHS"].strip(), value.strip()))

        if op == "=":
            return eqs
        elif op == "!=":
            return not eqs
        elif op == "~=":
            return reg
        else:
            return not reg


class NotNode(Node):
    """
    A **NOT** *Node*.
    """

    def __init__(self, node):
        """
        :param Node node: The node to be negated
        """
        if not isinstance(node, Node):
            raise InvalidExpression(f"{node!r} is not a valid Node")

        super().__init__("NOT", [node])

    def eval(self, ref):
        return not self.children[0].eval(ref)


class AllNode(Node):
    """
    A **AND** *Node*.
    """

    def __init__(self, nodes):
        """
        :param list(Node) nodes: A list of nodes that all must individually match
            the condition.
        """
        if not all([isinstance(node, Node) for node in nodes]):
            raise InvalidExpression("Not every node is valid Node")

        super().__init__("ALL", nodes)

    def eval(self, ref):
        return all([n.eval(ref) for n in self.children])


class AnyNode(Node):
    """
    A **OR** *Node*.
    """

    def __init__(self, nodes):
        """
        :param list(Node) nodes: A list of nodes. Only one must match
            the condition.
        """
        if not all([isinstance(node, Node) for node in nodes]):
            raise InvalidExpression("Not every node is valid Node")

        super().__init__("ANY", nodes)

    def eval(self, ref):
        return any([n.eval(ref) for n in self.children])


def parse_from_object(obj):
    """
    Parses the condition from a dictionary.

    :param dict obj: The dictionary containing the condition.
        See `condition dictionary`_ for the structure of the
        dictionary.
    :return: The node representing the out-most operator of the condition
    :rtype: Node
    """
    if isinstance(obj, str):
        return LiteralNode(obj)

    if isinstance(obj, dict):
        if len(obj) != 1:
            raise InvalidExpression("dictionary must have one key only")

        key = next(iter(obj.keys()))
        if key.lower() not in ("any", "all", "not"):
            raise InvalidExpression(f"{key!r} is not a valid operand")

        value = obj[key]
        key = key.lower()

        if key == "not":
            if not isinstance(value, list):
                raise InvalidExpression("NOT operand expects a list")
            if len(value) != 1:
                raise InvalidExpression(
                    "NOT operand expects only one element in the list"
                )
            return NotNode(parse_from_object(value[0]))
        elif key == "any":
            if not isinstance(value, list):
                raise InvalidExpression("ANY operand expects a list")
            return AnyNode([parse_from_object(x) for x in value])
        elif key == "all":
            if not isinstance(value, list):
                raise InvalidExpression("ALL operand expects a list")
            return AllNode([parse_from_object(x) for x in value])
    else:
        raise InvalidExpression(f"{obj!r} needs to be either a string or a dictionary")
