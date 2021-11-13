from .checker import parse_from_object


class Rule:
    """
    This class reprents a rule. A rule is the cobination of a condition and action.
    If the condition matches, the action can be executed.
    """

    def __init__(self, condition, action):
        """
        :param checker.Node condition: A Node object that holds the condition
        :param any action: the action. This object just stores the action,
            it doesn't manipulate it. Hence you can set any object you like.
        """
        self.condition = condition
        self.action = action

    def matches(self, obj):
        """
        Return whether the condition matches the object

        :param dict obj: The object with which the condition
            is checked. See :py:mod:`checker` for more information
            about the shape of the object.
        :return: ``True`` if the condition matches, ``False`` otherwise
        :rtype: bool
        """
        return self.condition.eval(obj)

    @classmethod
    def from_dict(cls, obj):
        """
        Generates a new :py:class:`Rule` object from a dictionary.

        The dictionary must have two key:

        - condition: see :any:`condition dictionary` for more information
        - action: an object (usually string) with the action to be taken
            when the condition matches

        :return: A new rule
        :rtype: Rule
        :raise checker.InvalidExpression: when parsing the condition fails
        """
        condition = parse_from_object(obj["condition"])
        action = obj["action"]

        return cls(condition, action)
