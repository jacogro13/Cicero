class Message:
    """Base for anything flowing through the bus (ADR-011)."""


class Command(Message):
    """An imperative request, handled by exactly one handler."""


class Event(Message):
    """A past-tense fact, handled by zero or more handlers."""
