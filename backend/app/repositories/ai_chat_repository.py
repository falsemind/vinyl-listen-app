from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from app.models.ai_chat import AiChatMessageRecord, AiChatSession


class AiChatRepository:
    @staticmethod
    def get_session(db: Session, conversation_id: str) -> AiChatSession | None:
        return db.get(AiChatSession, conversation_id)

    @staticmethod
    def get_or_create_session(db: Session, conversation_id: str) -> AiChatSession:
        session = AiChatRepository.get_session(db, conversation_id)
        if session is not None:
            return session

        now = datetime.now(UTC)
        session = AiChatSession(id=conversation_id, created_at=now, updated_at=now)
        db.add(session)
        db.flush()
        return session

    @staticmethod
    def list_messages(
        db: Session,
        conversation_id: str,
        *,
        limit: int | None = None,
    ) -> list[AiChatMessageRecord]:
        query = (
            db.query(AiChatMessageRecord)
            .filter(AiChatMessageRecord.conversation_id == conversation_id)
            .order_by(AiChatMessageRecord.created_at.asc(), AiChatMessageRecord.id.asc())
        )
        if limit is None:
            return query.all()

        recent_messages = (
            db.query(AiChatMessageRecord)
            .filter(AiChatMessageRecord.conversation_id == conversation_id)
            .order_by(AiChatMessageRecord.created_at.desc(), AiChatMessageRecord.id.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(recent_messages))

    @staticmethod
    def append_turn(
        db: Session,
        *,
        conversation_id: str,
        user_content: str,
        assistant_content: str,
        used_tools: list[str],
        client_context: dict[str, str] | None,
    ) -> tuple[AiChatMessageRecord, AiChatMessageRecord]:
        session = AiChatRepository.get_or_create_session(db, conversation_id)
        now = datetime.now(UTC)
        session.updated_at = now
        user_message = AiChatMessageRecord(
            conversation_id=conversation_id,
            role="user",
            content=user_content,
            used_tools=[],
            client_context=client_context,
            created_at=now,
        )
        assistant_message = AiChatMessageRecord(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            used_tools=used_tools,
            client_context=None,
            created_at=now + timedelta(microseconds=1),
        )
        db.add_all([user_message, assistant_message])
        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)
        return user_message, assistant_message

    @staticmethod
    def delete_conversation(db: Session, conversation_id: str) -> int:
        deleted_messages = (
            db.query(func.count(AiChatMessageRecord.id))
            .filter(AiChatMessageRecord.conversation_id == conversation_id)
            .scalar()
            or 0
        )
        db.execute(delete(AiChatMessageRecord).where(AiChatMessageRecord.conversation_id == conversation_id))
        db.execute(delete(AiChatSession).where(AiChatSession.id == conversation_id))
        db.commit()
        return deleted_messages
