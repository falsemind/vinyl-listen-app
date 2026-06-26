import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.ai.chat_adapter import AiChatAdapterError, AiChatAdapterReply, AiChatHistoryMessage, AiChatToolResult
from app.models.ai_chat import AiChatMessageRecord, AiChatSession
from app.models.auth import UserAccount
from app.services.ai_insights_service import (
    PROVIDER_UNAVAILABLE_CONTENT,
    AiInsightsService,
    AiInsightsValidationError,
)


class StubAiChatAdapter:
    provider_name = "stub"
    calls: list[dict[str, object]]
    error: AiChatAdapterError | None

    def __init__(self, reply: AiChatAdapterReply | None = None) -> None:
        self.calls = []
        self.error = None
        self.reply = reply or AiChatAdapterReply(content="Adapter response", used_tools=[])

    def generate_reply(
        self,
        *,
        message: str,
        conversation_id: str,
        client_context: dict[str, str] | None = None,
        history: list[AiChatHistoryMessage] | None = None,
        tool_context: list[AiChatToolResult] | None = None,
    ) -> AiChatAdapterReply:
        self.calls.append(
            {
                "message": message,
                "conversation_id": conversation_id,
                "client_context": client_context,
                "history": history or [],
                "tool_context": tool_context or [],
            }
        )
        if self.error is not None:
            raise self.error
        return self.reply


class StubAiInsightToolRunner:
    def __init__(self, results: list[AiChatToolResult] | None = None) -> None:
        self.results = results or []

    def run(self, db: Session, *, user_id: str, message: str) -> list[AiChatToolResult]:
        _ = db, user_id, message
        return self.results


def make_service(
    *,
    adapter: StubAiChatAdapter | None = None,
    tool_results: list[AiChatToolResult] | None = None,
) -> AiInsightsService:
    return AiInsightsService(
        adapter=adapter or StubAiChatAdapter(),
        tool_runner=StubAiInsightToolRunner(tool_results),
    )


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserAccount.__table__.create(engine)
    AiChatSession.__table__.create(engine)
    AiChatMessageRecord.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as db:
        db.add(
            UserAccount(
                id="user-a",
                email="user-a@example.com",
                password_hash="hash",
                normalized_email="user-a@example.com",
                password_hash_algorithm="argon2id",
                email_verified_at=None,
            )
        )
        db.add(
            UserAccount(
                id="user-b",
                email="user-b@example.com",
                password_hash="hash",
                normalized_email="user-b@example.com",
                password_hash_algorithm="argon2id",
                email_verified_at=None,
            )
        )
        db.commit()
        yield db


def test_chat_returns_adapter_reply_with_existing_conversation_id(db_session: Session) -> None:
    adapter = StubAiChatAdapter(reply=AiChatAdapterReply(content="You explored ambient most.", used_tools=["summary"]))
    tool_result = AiChatToolResult(name="get_style_distribution", content="Ambient: 4")
    service = make_service(adapter=adapter, tool_results=[tool_result])

    reply = service.chat(
        db=db_session,
        user_id="user-a",
        message="  What style did I explore most this month?  ",
        conversation_id="conversation-123",
        client_context={"timezone": "America/Los_Angeles"},
    )

    assert reply.conversation_id == "conversation-123"
    assert reply.content == "You explored ambient most."
    assert reply.used_tools == ["get_style_distribution", "summary"]
    assert adapter.calls == [
        {
            "message": "What style did I explore most this month?",
            "conversation_id": "conversation-123",
            "client_context": {"timezone": "America/Los_Angeles"},
            "history": [],
            "tool_context": [tool_result],
        }
    ]
    history = service.get_history(db_session, user_id="user-a", conversation_id="conversation-123")
    assert [(message.role, message.content) for message in history.messages] == [
        ("user", "What style did I explore most this month?"),
        ("assistant", "You explored ambient most."),
    ]


def test_chat_locks_account_data_before_persisting_reply(db_session: Session, monkeypatch) -> None:
    service = make_service()
    locked_user_ids: list[str] = []

    def record_account_data_lock(_db, *, user_id: str, repository=None) -> None:
        _ = repository
        locked_user_ids.append(user_id)

    monkeypatch.setattr(
        "app.services.ai_insights_service.lock_account_data_mutation",
        record_account_data_lock,
    )

    service.chat(db=db_session, user_id="user-a", message="Recommend a record")

    assert locked_user_ids == ["user-a"]


def test_chat_uses_default_single_thread_conversation_id(db_session: Session) -> None:
    adapter = StubAiChatAdapter()
    service = make_service(adapter=adapter)

    reply = service.chat(db=db_session, user_id="user-a", message="Recommend a record from my collection")

    assert reply.conversation_id == AiInsightsService.DEFAULT_CONVERSATION_ID
    assert adapter.calls[0]["conversation_id"] == AiInsightsService.DEFAULT_CONVERSATION_ID


def test_default_conversation_history_is_scoped_by_user(db_session: Session) -> None:
    service = make_service()

    service.chat(db=db_session, user_id="user-a", message="User A question")
    service.chat(db=db_session, user_id="user-b", message="User B question")

    user_a_history = service.get_history(db_session, user_id="user-a")
    user_b_history = service.get_history(db_session, user_id="user-b")

    assert [message.content for message in user_a_history.messages] == ["User A question", "Adapter response"]
    assert [message.content for message in user_b_history.messages] == ["User B question", "Adapter response"]


def test_chat_returns_safe_reply_when_adapter_fails(db_session: Session) -> None:
    adapter = StubAiChatAdapter()
    adapter.error = AiChatAdapterError("provider unavailable")
    service = make_service(adapter=adapter)

    reply = service.chat(db=db_session, user_id="user-a", message="What should I listen to?")

    assert reply.content == PROVIDER_UNAVAILABLE_CONTENT
    assert reply.used_tools == []
    assert service.get_history(db_session, user_id="user-a").messages[-1].content == PROVIDER_UNAVAILABLE_CONTENT


def test_chat_passes_persisted_history_to_adapter(db_session: Session) -> None:
    adapter = StubAiChatAdapter()
    service = make_service(adapter=adapter)

    service.chat(db=db_session, user_id="user-a", message="First question")
    service.chat(db=db_session, user_id="user-a", message="Second question")

    second_call_history = adapter.calls[1]["history"]
    assert second_call_history == [
        AiChatHistoryMessage(role="user", content="First question"),
        AiChatHistoryMessage(role="assistant", content="Adapter response"),
    ]


def test_clear_history_deletes_persisted_messages(db_session: Session) -> None:
    service = make_service()
    service.chat(db=db_session, user_id="user-a", message="Hello")

    result = service.clear_history(db_session, user_id="user-a")

    assert result.deleted_messages == 2
    assert service.get_history(db_session, user_id="user-a").messages == []


def test_chat_rejects_blank_message(db_session: Session) -> None:
    service = make_service()

    with pytest.raises(AiInsightsValidationError) as error:
        service.chat(db=db_session, user_id="user-a", message="   ")

    assert error.value.code == "empty_message"
    assert error.value.message == "message must not be blank."


def test_chat_rejects_blank_conversation_id(db_session: Session) -> None:
    service = make_service()

    with pytest.raises(AiInsightsValidationError) as error:
        service.chat(db=db_session, user_id="user-a", message="Hello", conversation_id="   ")

    assert error.value.code == "empty_conversation_id"
    assert error.value.message == "conversation_id must not be blank when provided."


def test_chat_rejects_long_conversation_id(db_session: Session) -> None:
    service = make_service()

    with pytest.raises(AiInsightsValidationError) as error:
        service.chat(db=db_session, user_id="user-a", message="Hello", conversation_id="x" * 37)

    assert error.value.code == "invalid_conversation_id"
    assert error.value.message == "conversation_id must be 36 characters or fewer."
