"""The message bus: one entry point for commands and events (ADR-011).

A command routes to one handler, an event to zero or more; the bus then drains
the UoW's new events until the queue empties.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from cicero.domain.messages import Command, Event, Message
from cicero.domain.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

CommandHandler = Callable[[Command, UnitOfWork], Awaitable[Any]]
EventHandler = Callable[[Event, UnitOfWork], Awaitable[None]]


class MessageBus:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        command_handlers: dict[type[Command], CommandHandler],
        event_handlers: dict[type[Event], list[EventHandler]],
    ) -> None:
        self._uow_factory = uow_factory
        self._command_handlers = command_handlers
        self._event_handlers = event_handlers

    async def handle(self, message: Message) -> Any:
        """Process a message and every event it transitively raises, returning the
        originating command's result (ADR-011/012)."""
        uow = self._uow_factory()
        queue: deque[Message] = deque([message])
        result: Any = None
        originating = True
        while queue:
            message = queue.popleft()
            if isinstance(message, Command):
                handled = await self._command_handlers[type(message)](message, uow)
                if originating:
                    result = handled
            elif isinstance(message, Event):
                for handler in self._event_handlers.get(type(message), []):
                    await handler(message, uow)
            else:
                raise TypeError(f"not a Command or Event: {message!r}")
            originating = False
            queue.extend(uow.collect_new_events())
        return result
