from datetime import datetime, timezone, timedelta
from typing import Optional, List
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AppError, ErrorCode
from src.models.learning import (
    LearningGoal, PlanDraft, LearningTrack, Topic, LearningMaterial,
    PlanStatus, TrackStatus, TopicStatus,
)
from src.models.exam import Exam
from src.models.user import CurrentLevel
from src.adapters.ai_adapter import AIAdapter
from src.adapters.source_checker import SourceChecker


class PlanService:
    """Сервис для работы с планами (раздел 6.3-6.4 ТЗ)"""
    
    def __init__(self, db: AsyncSession, ai: AIAdapter):
        self.db = db
        self.ai = ai
        self.source_checker = SourceChecker()
    
    # === Интервью ===
    async def create_or_get_interview(self, user_id: uuid.UUID, interview_id: Optional[uuid.UUID] = None):
        if interview_id:
            result = await self.db.execute(
                select(PlanDraft).join(LearningGoal).where(
                    PlanDraft.id == interview_id,
                    LearningGoal.user_id == user_id,
                )
            )
            plan = result.scalar_one_or_none()
            if plan:
                return plan
        
        # Создаем новую цель + черновик
        goal = LearningGoal(
            user_id=user_id,
            skill="",
            target_outcome="",
            current_level=CurrentLevel.BEGINNER,
            target_date=datetime.now(timezone.utc).date(),
            hours_per_week=5.0,
            preferred_formats=[],
            constraints=[],
            accepted_risk=False,
        )
        self.db.add(goal)
        await self.db.flush()
        
        plan = PlanDraft(
            goal_id=goal.id,
            status=PlanStatus.COLLECTING,
            assumptions=[],
            gaps=[],
            topics_data=[],
        )
        self.db.add(plan)
        await self.db.commit()
        return plan
    
    async def save_brief_field(self, plan_id: uuid.UUID, user_id: uuid.UUID,
                               field: str, value, expected_version: int):
        plan = await self._get_owned_plan(plan_id, user_id)
        if plan.version != expected_version:
            raise AppError(
                code=ErrorCode.VERSION_CONFLICT,
                message="Версия интервью устарела",
                status_code=409,
                details={"currentVersion": plan.version},
            )
        
        goal = await self._get_goal(plan.goal_id)
        
        field_map = {
            "skill": "skill",
            "targetOutcome": "target_outcome",
            "currentLevel": "current_level",
            "targetDate": "target_date",
            "hoursPerWeek": "hours_per_week",
            "preferredFormats": "preferred_formats",
            "constraints": "constraints",
            "acceptedRisk": "accepted_risk",
        }
        db_field = field_map.get(field)
        if not db_field:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Неизвестное поле: {field}",
                status_code=400,
            )
        
        # Приводим типы
        if field == "targetDate" and isinstance(value, str):
            value = datetime.fromisoformat(value).date()
        elif field == "currentLevel":
            value = CurrentLevel(value)
        elif field == "hoursPerWeek":
            value = float(value)
        
        setattr(goal, db_field, value)
        
        # Сброс deadline evaluation при изменении ключевых полей
        if field in ("skill", "targetOutcome", "targetDate", "hoursPerWeek"):
            goal.deadline_risk = None
        
        plan.version += 1
        await self.db.commit()
        return plan, goal
    
    async def evaluate_deadline(self, data: dict) -> dict:
        return await self.ai.evaluate_deadline(
            skill=data["skill"],
            target_outcome=data["targetOutcome"],
            current_level=data["currentLevel"],
            target_date=data["targetDate"],
            hours_per_week=data["hoursPerWeek"],
        )
    
    async def generate_plan(self, plan_id: uuid.UUID, user_id: uuid.UUID,
                            brief_version: int, accepted_assumption_ids: List[str]):
        plan = await self._get_owned_plan(plan_id, user_id)
        goal = await self._get_goal(plan.goal_id)
        
        # Проверка полноты brief
        missing = self._check_brief_completeness(goal)
        if missing:
            raise AppError(
                code=ErrorCode.BUSINESS_RULE_VIOLATION,
                message="Заполните все обязательные поля",
                status_code=422,
                details={"missingFields": missing},
            )
        
        # Проверка high risk
        if goal.deadline_risk and goal.deadline_risk.value == "high" and not goal.accepted_risk:
            raise AppError(
                code=ErrorCode.BUSINESS_RULE_VIOLATION,
                message="Необходимо подтвердить риск дедлайна",
                status_code=422,
            )
        
        # Генерация через AI
        brief = {
            "skill": goal.skill,
            "targetOutcome": goal.target_outcome,
            "currentLevel": goal.current_level.value,
            "targetDate": goal.target_date.isoformat(),
            "hoursPerWeek": goal.hours_per_week,
            "preferredFormats": goal.preferred_formats,
            "constraints": goal.constraints,
        }
        
        result = await self.ai.generate_plan(brief)
        
        # Проверка источников
        gaps = list(result.get("gaps", []))
        for topic_data in result.get("topics", []):
            for material in topic_data.get("materials", []):
                check = await self.source_checker.check(material["url"])
                material["verificationStatus"] = check["status"]
                material["checkedAt"] = check["checkedAt"]
                material["domain"] = check.get("domain") or material.get("domain")
        
        plan.status = PlanStatus.DRAFT
        plan.assumptions = result.get("assumptions", [])
        plan.gaps = gaps
        plan.topics_data = result.get("topics", [])
        plan.version += 1
        
        await self.db.commit()
        return plan
    
    async def _get_owned_plan(self, plan_id: uuid.UUID, user_id: uuid.UUID) -> PlanDraft:
        result = await self.db.execute(
            select(PlanDraft).join(LearningGoal).where(
                PlanDraft.id == plan_id,
                LearningGoal.user_id == user_id,
            )
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Программа не найдена",
                status_code=404,
            )
        return plan
    
    async def _get_goal(self, goal_id: uuid.UUID) -> LearningGoal:
        result = await self.db.execute(
            select(LearningGoal).where(LearningGoal.id == goal_id)
        )
        return result.scalar_one()
    
    def _check_brief_completeness(self, goal: LearningGoal) -> List[str]:
        missing = []
        if not goal.skill or len(goal.skill) < 2:
            missing.append("skill")
        if not goal.target_outcome or len(goal.target_outcome) < 5:
            missing.append("targetOutcome")
        if goal.hours_per_week <= 0:
            missing.append("hoursPerWeek")
        return missing
    
    # === Approve: превращение плана в трек ===
    async def approve_plan(self, plan_id: uuid.UUID, user_id: uuid.UUID,
                           expected_version: int, acknowledgements: dict) -> LearningTrack:
        plan = await self._get_owned_plan(plan_id, user_id)
        if plan.version != expected_version:
            raise AppError(
                code=ErrorCode.VERSION_CONFLICT,
                message="Версия плана устарела",
                status_code=409,
                details={"currentVersion": plan.version},
            )
        
        # Проверка acknowledgement всех warning gaps
        accepted_gap_ids = set(acknowledgements.get("acceptedGapIds", []))
        for gap in plan.gaps:
            if gap.get("severity") == "warning" and gap.get("id") not in accepted_gap_ids:
                raise AppError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message="Не все предупреждения подтверждены",
                    status_code=422,
                    details={"unacknowledgedGapIds": [gap["id"] for gap in plan.gaps
                                                       if gap.get("severity") == "warning"
                                                       and gap.get("id") not in accepted_gap_ids]},
                )
        
        goal = await self._get_goal(plan.goal_id)
        
        # Создаем Track
        track = LearningTrack(
            title=goal.skill,
            goal_id=goal.id,
            plan_id=plan.id,
            plan_version=plan.version,
            status=TrackStatus.ACTIVE,
            progress_percent=0.0,
        )
        self.db.add(track)
        await self.db.flush()
        
        # Создаем темы и материалы
        topic_id_map = {}
        previous_topic_id = None
        for idx, topic_data in enumerate(plan.topics_data):
            topic = Topic(
                track_id=track.id,
                title=topic_data["title"],
                outcome=topic_data.get("outcome", ""),
                order=topic_data.get("order", idx + 1),
                prerequisite_topic_ids=[],
                status=TopicStatus.LOCKED if idx > 0 else TopicStatus.AVAILABLE,
                progress_percent=0.0,
            )
            self.db.add(topic)
            await self.db.flush()
            topic_id_map[topic_data.get("id", f"topic-{idx}")] = topic.id
            
            # Материалы
            for m in topic_data.get("materials", []):
                material = LearningMaterial(
                    topic_id=topic.id,
                    title=m["title"],
                    type=m.get("type", "article"),
                    url=m["url"],
                    domain=m.get("domain", ""),
                    source_name=m.get("sourceName", ""),
                    language=m.get("language", "ru"),
                    required=m.get("required", True),
                    verification_status=m.get("verificationStatus", "unverified"),
                    checked_at=datetime.now(timezone.utc),
                    completed=False,
                )
                self.db.add(material)
        
        # Устанавливаем currentTopic
        first_topic_id = topic_id_map.get(plan.topics_data[0].get("id", "topic-0"))
        track.current_topic_id = first_topic_id
        
        # Обновляем план
        plan.status = PlanStatus.APPROVED
        
        await self.db.commit()
        return track