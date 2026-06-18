class DomainError(Exception):
    """Base for errors the domain raises on a broken rule or invariant (ADR-008).

    The domain signals failure; it never names an HTTP status. The
    ``entrypoints/`` layer maps subclasses to responses."""
