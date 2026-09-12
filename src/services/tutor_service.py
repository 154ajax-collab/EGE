from datetime import datetime, timezone
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AppError, ErrorCode
from src.models.chat import ChatThread, ChatMessage, ChatPurpose, MessageRole
from src.models.learning import LearningTrack, Topic, LearningMaterial, LearningGoal
from src.adapters.ai_adapter import AIAdapter


class TutorService:
    """Раздел 6.7 ТЗ"""
    
    def __init__(self, db: AsyncSession, ai: AIAdapter):
        self.db = db
        self.ai = ai
    
    async def create_or_get_thread(self, user_id: uuid.UUID, purpose: str = "tutor",
                                    track_id: Optional[uuid.UUID] = None) -> ChatThread:
        thread = ChatThread(
            user_id=user_id,
            track_id=track_id,
            plan_id=None,
            purpose=ChatPurpose(purpose),
            context_version=1,
            status="active",
        )
        self.db.add(thread)
        await self.db.commit()
        return thread
    
    async def set_context(self, thread_id: uuid.UUID, user_id: uuid.UUID,
                          topic_id: Optional[str], material_id: Optional[str],
                          expected_context_version: int) -> ChatThread:
        """FN-TUTOR-CONTEXT-SET"""
        thread = await self._get_owned_thread(thread_id, user_id)
        if thread.context_version != expected_context_version:
            raise AppError(ErrorCode.VERSION_CONFLICT, "Контекст устарел", 409)
        
        # Проверяем принадлежность topic/material к тому же track
        if topic_id and thread.track_id:
            result = await self.db.execute(
                select(Topic).where(
                    Topic.id == uuid.UUID(topic_id),
                    Topic.track_id == thread.track_id,
                )
            )
            if not result.scalar_one_or_none():
                raise AppError(ErrorCode.ACCESS_DENIED, "Тема недоступна", 403)
        
        thread.context_version += 1
        await self.db.commit()
        return thread
    
    async def send_message(self, thread_id: uuid.UUID, user_id: uuid.UUID,
                           text: str, context_version: int,
                           client_message_id: str) -> dict:
        """FN-TUTOR-SEND"""
        thread = await self._get_owned_thread(thread_id, user_id)
        
        if thread.context_version != context_version:
            raise AppError(ErrorCode.VERSION_CONFLICT, "Контекст устарел", 409)
        
        # Сохраняем user message
        user_msg = ChatMessage(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=text,
            references=[],
            status="sent",
        )
        self.db.add(user_msg)
        await self.db.flush()
        
        # Генерируем ответ AI
        context = await self._build_context(thread)
        ai_result = await self.ai.tutor_response(context, text)
        
        assistant_msg = ChatMessage(
            thread_id=thread.id,
            role=MessageRole.ASSISTANT,
            content=ai_result["content"],
            references=ai_result.get("references", []),
            status="complete",
        )
        self.db.add(assistant_msg)
        await self.db.commit()
        
        return {
            "id": f"run-{assistant_msg.id}",
            "threadId": str(thread.id),
            "userMessageId": str(user_msg.id),
            "assistantMessageId": str(assistant_msg.id),
            "status": "complete",
            "contextVersion": thread.context_version,
        }
    
    async def get_history(self, thread_id: uuid.UUID, user_id: uuid.UUID,
                          cursor: Optional[str] = None) -> dict:
        thread = await self._get_owned_thread(thread_id, user_id)
        result = await self.db.execute(
            select(ChatMessage).where(ChatMessage.thread_id == thread.id)
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()
        return {
            "messages": [
                {
                    "id": str(m.id),
                    "role": m.role.value,
                    "content": m.content,
                    "references": m.references or [],
                    "status": m.status,
                    "createdAt": m.created_at.isoformat(),
                }
                for m in messages
            ],
            "hasMore": False,
            "nextCursor": None,
        }
    
    async def summarize(self, thread_id: uuid.UUID, user_id: uuid.UUID,
                        material_id: str, context_version: int) -> dict:
        """FN-TUTOR-SUMMARIZE"""
        thread = await self._get_owned_thread(thread_id, user_id)
        
        result = await self.db.execute(
            select(LearningMaterial).where(LearningMaterial.id == uuid.UUID(material_id))
        )
        material = result.scalar_one_or_none()
        if not material:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Материал не найден", 404)
        
        # Mock: имитируем недоступность контента для unverified
        if material.verification_status.value == "broken":
            raise AppError(
                code=ErrorCode.BUSINESS_RULE_VIOLATION,
                message="Контент материала недоступен",
                status_code=422,
                details={"code": "MATERIAL_CONTENT_UNAVAILABLE"},
            )
        
        ai_result = await self.ai.tutor_response(
            {"material": material.title}, f"Сделай конспект: {material.title}"
        )
        
        assistant_msg = ChatMessage(
            thread_id=thread.id,
            role=MessageRole.ASSISTANT,
            content=ai_result["content"],
            references=[{"materialId": str(material.id), "url": material.url}],
            status="complete",
        )
        self.db.add(assistant_msg)
        await self.db.commit()
        
        return {
            "id": f"run-{assistant_msg.id}",
            "threadId": str(thread.id),
            "status": "complete",
            "assistantMessageId": str(assistant_msg.id),
        }
    
    async def practice(self, thread_id: uuid.UUID, user_id: uuid.UUID,
                       topic_id: str, difficulty: Optional[str] = None,
                       question_count: int = 3, context_version: int = 1) -> dict:
        """FN-TUTOR-PRACTICE"""
        thread = await self._get_owned_thread(thread_id, user_id)
        
        # Mock: генерируем простые вопросы
        questions = [
            {"id": f"pq-{i}", "type": "text", "text": f"Вопрос {i+1} по теме"}
            for i in range(question_count)
        ]
        
        return {
            "id": f"practice-{uuid.uuid4()}",
            "status": "active",
            "topicId": topic_id,
            "questions": questions,
            "currentIndex": 0,
            "feedback": None,
        }
    
    async def feedback(self, message_id: uuid.UUID, user_id: uuid.UUID,
                       rating: str, reason_code: Optional[str] = None,
                       comment: Optional[str] = None) -> None:
        """FN-TUTOR-FEEDBACK — сохраняем только логирование для MVP"""
        result = await self.db.execute(
            select(ChatMessage).join(ChatThread).where(
                ChatMessage.id == message_id,
                ChatThread.user_id == user_id,
            )
        )
        if not result.scalar_one_or_none():
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Сообщение не найдено", 404)
        # Для MVP не сохраняем — только логируем (раздел 11 ТЗ)
    
    async def _get_owned_thread(self, thread_id: uuid.UUID, user_id: uuid.UUID) -> ChatThread:
        result = await self.db.execute(
            select(ChatThread).where(
                ChatThread.id == thread_id,
                ChatThread.user_id == user_id,
            )
        )
        thread = result.scalar_one_or_none()
        if not thread:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Чат не найден", 404)
        return thread
    
    async def _build_context(self, thread: ChatThread) -> dict:
        ctx = {"threadPurpose": thread.purpose.value}
        if thread.track_id:
            result = await self.db.execute(
                select(LearningTrack).where(LearningTrack.id == thread.track_id)
            )
            track = result.scalar_one_or_none()
            if track:
                ctx["track"] = {"id": str(track.id), "title": track.title}
        return ctx