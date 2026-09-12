from datetime import datetime, timezone
from typing import List, Optional
import uuid

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.learning import LearningTrack, Topic, TrackStatus, TopicStatus
from src.models.exam import Exam, ExamAttempt, AttemptStatus
from src.models.learning import LearningGoal

class DashboardService:
    """FN-DASHBOARD-LOAD (раздел 6.2 ТЗ)"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def load_dashboard(
        self,
        user_id: uuid.UUID,
        filter_type: str = "active",
    ) -> dict:
        # Определяем статусы по фильтру
        status_map = {
            "active": [TrackStatus.ACTIVE],
            "attention": [TrackStatus.ACTIVE],  # attention — из активных с рисками
            "completed": [TrackStatus.COMPLETED],
        }
        statuses = status_map.get(filter_type, [TrackStatus.ACTIVE])
        
        # Получаем треки
        result = await self.db.execute(
            select(LearningTrack).where(
                LearningTrack.goal_id.in_(
                    select(LearningGoal.id).where(LearningGoal.user_id == user_id)
                ),
                LearningTrack.status.in_(statuses),
            )
        )
        tracks = result.scalars().all()
        
        # Формируем карточки
        cards = []
        now = datetime.now(timezone.utc)
        attention_count = 0
        next_deadline_global = None
        
        for track in tracks:
            # Получаем текущую тему
            current_topic = None
            if track.current_topic_id:
                topic_result = await self.db.execute(
                    select(Topic).where(Topic.id == track.current_topic_id)
                )
                current_topic = topic_result.scalar_one_or_none()
            
            # Определяем риск
            risk_status = None
            if track.next_deadline and track.next_deadline < now:
                risk_status = "overdue"
                attention_count += 1
            elif track.next_deadline and (track.next_deadline - now).days <= 3:
                risk_status = "due_soon"
            
            # Обновляем глобальный next_deadline
            if track.next_deadline:
                if next_deadline_global is None or track.next_deadline < next_deadline_global:
                    next_deadline_global = track.next_deadline
            
            # Определяем nextAction
            next_action = self._determine_next_action(track, current_topic)
            
            cards.append({
                "id": str(track.id),
                "title": track.title,
                "status": track.status.value,
                "progressPercent": track.progress_percent,
                "currentTopic": {
                    "id": str(current_topic.id),
                    "title": current_topic.title,
                } if current_topic else None,
                "nextAction": next_action,
                "nextDeadline": track.next_deadline.isoformat() if track.next_deadline else None,
                "riskStatus": risk_status,
                "version": track.version,
            })
        
        # Сортировка: overdue/attention → ближайший deadline → недавно открытый
        cards.sort(key=lambda c: (
            0 if c["riskStatus"] == "overdue" else 1,
            c["nextDeadline"] or "9999",
        ))
        
        return {
            "summary": {
                "activeTrackCount": len([c for c in cards if c["status"] == "active"]),
                "attentionCount": attention_count,
                "nextDeadline": next_deadline_global.isoformat() if next_deadline_global else None,
            },
            "tracks": cards,
            "partialErrors": [],
        }
    
    def _determine_next_action(self, track, current_topic) -> Optional[str]:
        if not current_topic:
            return "open_track"
        if current_topic.status == TopicStatus.LOCKED:
            return "open_prerequisite"
        if current_topic.status == TopicStatus.AVAILABLE:
            return "start_topic"
        if current_topic.status == TopicStatus.IN_PROGRESS:
            return "continue_topic"
        if current_topic.status == TopicStatus.READY_FOR_EXAM:
            return "start_exam"
        return "continue_topic"
