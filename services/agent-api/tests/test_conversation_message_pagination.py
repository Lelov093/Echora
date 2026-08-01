"""Latest-message pagination contract."""

import uuid
from types import SimpleNamespace

from app.db.models import Conversation, Message
from app.services import conversation_service


class _Result:
    def __init__(self, *, scalar_value=None, items=None):
        self._scalar_value = scalar_value
        self._items = items or []

    def scalar(self):
        return self._scalar_value

    def scalars(self):
        return self

    def all(self):
        return self._items


class _Session:
    def __init__(self, conversation):
        self.conversation = conversation
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, model, record_id):
        if model is Conversation and record_id == self.conversation.id:
            return self.conversation
        return None

    def execute(self, statement):
        self.statements.append(statement)
        if len(self.statements) == 1:
            return _Result(scalar_value=75)
        return _Result(items=[])


def test_latest_message_page_has_stable_descending_order(monkeypatch):
    conversation = SimpleNamespace(
        id=uuid.uuid4(),
        companion_id=uuid.uuid4(),
        deleted_at=None,
        retention_expires_at=None,
        metadata_={},
    )
    session = _Session(conversation)
    monkeypatch.setattr(conversation_service, "get_session", lambda: session)

    result = conversation_service.list_messages(
        conversation.id,
        conversation.companion_id,
        page=1,
        page_size=50,
        descending=True,
    )

    statement = str(session.statements[1])
    assert result["total"] == 75
    assert "messages.created_at DESC" in statement
    assert "messages.id DESC" in statement
    assert "LIMIT" in statement
