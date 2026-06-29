"""The message bus: one `handle()` for commands and events (ADR-011).

A command goes to exactly one handler; an event to zero or more. After each
handler the bus drains the UoW's new events and keeps processing, so a handler
that touches an aggregate causes that aggregate's events to be dispatched.
"""

from dataclasses import dataclass

import pytest

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.events import DocumentUploaded
from cicero.domain.messages import Command, Event
from cicero.domain.ports.unit_of_work import UnitOfWork
from cicero.services.messagebus import MessageBus

from tests.fakes import make_in_memory_uow_factory


@dataclass(frozen=True)
class _CreateDocument(Command):
    title: str


async def _create_document(command: _CreateDocument, uow: UnitOfWork) -> Document:
    document = Document.create(command.title)
    async with uow:
        await uow.documents.save(document)
        await uow.commit()
    return document


class TestMessageBus:
    async def test_command_is_routed_to_its_handler_and_the_result_returned(self):
        async def handle(command: _CreateDocument, uow: UnitOfWork) -> str:
            return f"handled:{command.title}"

        bus = MessageBus(
            make_in_memory_uow_factory(),
            command_handlers={_CreateDocument: handle},
            event_handlers={},
        )

        assert await bus.handle(_CreateDocument(title="x")) == "handled:x"

    async def test_events_raised_by_a_handler_are_dispatched(self):
        received: list[Event] = []

        async def record(event: DocumentUploaded, uow: UnitOfWork) -> None:
            received.append(event)

        bus = MessageBus(
            make_in_memory_uow_factory(),
            command_handlers={_CreateDocument: _create_document},
            event_handlers={DocumentUploaded: [record]},
        )

        document = await bus.handle(_CreateDocument(title="Domain-Driven Design"))

        assert received == [DocumentUploaded(document_id=document.id)]

    async def test_handling_an_event_returns_no_result(self):
        # The return value is the originating *command*'s result; dispatching an
        # event directly yields nothing, even when handlers run.
        received: list[Event] = []

        async def record(event: DocumentUploaded, uow: UnitOfWork) -> None:
            received.append(event)

        bus = MessageBus(
            make_in_memory_uow_factory(),
            command_handlers={},
            event_handlers={DocumentUploaded: [record]},
        )

        result = await bus.handle(DocumentUploaded(document_id=DocumentId.new()))

        assert result is None
        assert len(received) == 1

    async def test_an_event_with_no_handler_is_ignored(self):
        bus = MessageBus(
            make_in_memory_uow_factory(),
            command_handlers={_CreateDocument: _create_document},
            event_handlers={},
        )

        # The DocumentUploaded the handler raises has no subscriber — handled silently.
        await bus.handle(_CreateDocument(title="x"))

    async def test_an_unknown_command_raises(self):
        bus = MessageBus(
            make_in_memory_uow_factory(), command_handlers={}, event_handlers={}
        )

        with pytest.raises(KeyError):
            await bus.handle(_CreateDocument(title="x"))
