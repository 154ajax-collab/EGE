from datetime import datetime, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AppError, ErrorCode
from src.models.learning import (
    LearningTrack, Topic, LearningMaterial, LearningGoal,
    TrackStatus, TopicStatus, MaterialVerificationStatus,
)
from src.models.exam import Exam


class LearningService:
    """Раздел 6.5 ТЗ"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_track(self, track_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """FN-TRACK-OPEN"""
        track = await self._get_owned_track(track_id, user_id)
        
        topics_result = await self.db.execute(
            select(Topic).where(Topic.track_id == track.id).order_by(Topic.order)
        )
        topics = topics_result.scalars().all()
        
        return {
            "track": self._serialize_track(track),
            "topics": [self._serialize_topic_short(t) for t in topics],
            "currentAction": self._determine_next_action(track, topics),
            "nextDeadline": track.next_deadline.isoformat() if track.next_deadline else None,
            "accessRulesVersion": 1,
        }
    
    async def get_topic(self, track_id: uuid.UUID, topic_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """FN-TOPIC-OPEN"""
        track = await self._get_owned_track(track_id, user_id)
        
        result = await self.db.execute(
            select(Topic).where(Topic.id == topic_id, Topic.track_id == track.id)
        )
        topic = result.scalar_one_or_none()
        if not topic:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Тема не найдена", 404)
        
        # Проверка prerequisites
        if topic.status == TopicStatus.LOCKED:
            raise AppError(
                code=ErrorCode.PREREQUISITE_LOCKED,
                message="Тема закрыта",
                status_code=403,
                details={"prerequisiteTopicIds": [str(pid) for pid in (topic.prerequisite_topic_ids or [])]},
            )
        
        materials_result = await self.db.execute(
            select(LearningMaterial).where(LearningMaterial.topic_id == topic.id)
        )
        materials = materials_result.scalars().all()
        
        return {
            "topic": self._serialize_topic_full(topic),
            "materials": [self._serialize_material(m) for m in materials],
            "selfCheckQuestions": [],
            "examSummary": {"id": str(topic.exam_id), "passingPercent": 80} if topic.exam_id else None,
            "access": {"allowed": True},
        }
    
    async def register_material_open(self, material_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """FN-MATERIAL-OPEN — только проверка доступа, event не пишем для MVP"""
        await self._get_owned_material(material_id, user_id)
    
    async def set_material_completion(self, material_id: uuid.UUID, user_id: uuid.UUID,
                                       completed: bool, expected_version: int) -> dict:
        """FN-MATERIAL-COMPLETE"""
        material = await self._get_owned_material(material_id, user_id)
        
        if material.version != expected_version:
            raise AppError(
                code=ErrorCode.VERSION_CONFLICT,
                message="Материал был изменён",
                status_code=409,
                details={"currentVersion": material.version},
            )
        
        material.completed = completed
        material.version += 1
        
        # Пересчет прогресса темы
        topic = await self._recalc_topic_progress(material.topic_id)
        track = await self._recalc_track_progress(topic.track_id)
        
        await self.db.commit()
        
        # Определяем examAccess
        exam_access = {
            "allowed": topic.status == TopicStatus.READY_FOR_EXAM or topic.status == TopicStatus.AVAILABLE,
            "reason": None,
        }
        
        return {
            "material": self._serialize_material(material),
            "topicSummary": self._serialize_topic_short(topic),
            "trackProgress": track.progress_percent,
            "examAccess": exam_access,
        }
    
    async def get_stats(self, track_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """FN-STATS-LOAD"""
        track = await self._get_owned_track(track_id, user_id)
        
        topics_result = await self.db.execute(
            select(Topic).where(Topic.track_id == track.id)
        )
        topics = topics_result.scalars().all()
        
        passed_topics = [t for t in topics if t.status == TopicStatus.PASSED]
        total_topics = len(topics)
        
        insufficient = len(passed_topics) < 2
        
        return {
            "nextDeadline": track.next_deadline.isoformat() if track.next_deadline else None,
            "calendarItems": [],
            "examSummary": {"passed": len(passed_topics), "total": total_topics},
            "topicSummary": {
                "passed": len(passed_topics),
                "total": total_topics,
            },
            "pace": None,
            "attentionItems": [],
            "insufficientData": insufficient,
        }
    
    # === Helpers ===
    
    async def _get_owned_track(self, track_id: uuid.UUID, user_id: uuid.UUID) -> LearningTrack:
        result = await self.db.execute(
            select(LearningTrack).join(LearningGoal).where(
                LearningTrack.id == track_id,
                LearningGoal.user_id == user_id,
            )
        )
        track = result.scalar_one_or_none()
        if not track:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Трек не найден", 404)
        return track
    
    async def _get_owned_material(self, material_id: uuid.UUID, user_id: uuid.UUID) -> LearningMaterial:
        result = await self.db.execute(
            select(LearningMaterial)
            .join(Topic, LearningMaterial.topic_id == Topic.id)
            .join(LearningTrack, Topic.track_id == LearningTrack.id)
            .join(LearningGoal, LearningTrack.goal_id == LearningGoal.id)
            .where(LearningMaterial.id == material_id, LearningGoal.user_id == user_id)
        )
        material = result.scalar_one_or_none()
        if not material:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Материал не найден", 404)
        return material
    
    async def _recalc_topic_progress(self, topic_id: uuid.UUID) -> Topic:
        result = await self.db.execute(
            select(Topic).where(Topic.id == topic_id)
        )
        topic = result.scalar_one()
        
        materials_result = await self.db.execute(
            select(LearningMaterial).where(
                LearningMaterial.topic_id == topic_id,
                LearningMaterial.required == True,
            )
        )
        materials = materials_result.scalars().all()
        if not materials:
            topic.progress_percent = 0.0
        else:
            done = sum(1 for m in materials if m.completed)
            topic.progress_percent = (done / len(materials)) * 100
        
        # Обновляем статус темы
        if topic.progress_percent >= 100 and topic.status != TopicStatus.PASSED:
            topic.status = TopicStatus.READY_FOR_EXAM
        elif topic.progress_percent > 0 and topic.status == TopicStatus.AVAILABLE:
            topic.status = TopicStatus.IN_PROGRESS
        
        return topic
    
    async def _recalc_track_progress(self, track_id: uuid.UUID) -> LearningTrack:
        result = await self.db.execute(
            select(LearningTrack).where(LearningTrack.id == track_id)
        )
        track = result.scalar_one()
        
        topics_result = await self.db.execute(
            select(Topic).where(Topic.track_id == track_id)
        )
        topics = topics_result.scalars().all()
        if not topics:
            track.progress_percent = 0.0
        else:
            passed = sum(1 for t in topics if t.status == TopicStatus.PASSED)
            track.progress_percent = (passed / len(topics)) * 100
        
        return track
    
    def _serialize_track(self, track: LearningTrack) -> dict:
        return {
            "id": str(track.id),
            "title": track.title,
            "status": track.status.value,
            "progressPercent": track.progress_percent,
            "currentTopicId": str(track.current_topic_id) if track.current_topic_id else None,
            "nextDeadline": track.next_deadline.isoformat() if track.next_deadline else None,
            "version": track.version,
        }
    
    def _serialize_topic_short(self, topic: Topic) -> dict:
        return {
            "id": str(topic.id),
            "title": topic.title,
            "order": topic.order,
            "status": topic.status.value,
            "progressPercent": topic.progress_percent,
            "examId": str(topic.exam_id) if topic.exam_id else None,
        }
    
    def _serialize_topic_full(self, topic: Topic) -> dict:
        return {
            **self._serialize_topic_short(topic),
            "outcome": topic.outcome,
            "prerequisiteTopicIds": [str(p) for p in (topic.prerequisite_topic_ids or [])],
            "deadline": topic.deadline.isoformat() if topic.deadline else None,
            "version": topic.version,
        }
    
    def _serialize_material(self, m: LearningMaterial) -> dict:
        return {
            "id": str(m.id),
            "title": m.title,
            "type": m.type,
            "url": m.url,
            "domain": m.domain,
            "sourceName": m.source_name,
            "language": m.language,
            "durationSec": m.duration_sec,
            "required": m.required,
            "verificationStatus": m.verification_status.value,
            "checkedAt": m.checked_at.isoformat() if m.checked_at else None,
            "completed": m.completed,
            "version": m.version,
        }
    
    def _determine_next_action(self, track, topics) -> str:
        if not topics:
            return "wait"
        for t in topics:
            if t.status == TopicStatus.AVAILABLE:
                return "start_topic"
            if t.status == TopicStatus.IN_PROGRESS:
                return "continue_topic"
            if t.status == TopicStatus.READY_FOR_EXAM:
                return "start_exam"
        return "completed" if track.status == TrackStatus.COMPLETED else "wait"