from datetime import datetime, timezone
import uuid
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import AppError, ErrorCode
from src.models.exam import Exam, ExamAttempt, AttemptStatus
from src.models.learning import Topic, TopicStatus, LearningTrack, TrackStatus
from src.models.user import User
from src.adapters.ai_adapter import AIAdapter


class ExamService:
    """Раздел 6.6 ТЗ"""
    
    def __init__(self, db: AsyncSession, ai: AIAdapter):
        self.db = db
        self.ai = ai
    
    async def get_exam_intro(self, exam_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        exam = await self._get_owned_exam(exam_id, user_id)
        return {
            "id": str(exam.id),
            "title": exam.title,
            "criteria": exam.criteria,
            "passingPercent": exam.passing_percent,
            "maxAttempts": exam.max_attempts,
            "cooldownSec": exam.cooldown_sec,
            "timeLimitSec": exam.time_limit_sec,
            "questionCount": exam.question_count,
            "final": exam.final,
        }
    
    async def start_attempt(self, exam_id: uuid.UUID, user_id: uuid.UUID,
                            resume_if_active: bool = True) -> dict:
        """FN-EXAM-START"""
        exam = await self._get_owned_exam(exam_id, user_id)
        
        # Ищем активную попытку
        if resume_if_active:
            result = await self.db.execute(
                select(ExamAttempt).where(
                    ExamAttempt.exam_id == exam.id,
                    ExamAttempt.status == AttemptStatus.ACTIVE,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return self._serialize_attempt_for_client(existing, exam)
        
        # Создаем новую попытку со snapshot
        attempt = ExamAttempt(
            exam_id=exam.id,
            status=AttemptStatus.ACTIVE,
            rubric_version=1,
            answers=[],
        )
        self.db.add(attempt)
        await self.db.commit()
        
        return self._serialize_attempt_for_client(attempt, exam)
    
    async def save_answer(self, attempt_id: uuid.UUID, question_id: str,
                          user_id: uuid.UUID, data: dict, expected_version: int) -> dict:
        """FN-EXAM-ANSWER-SAVE"""
        attempt = await self._get_owned_attempt(attempt_id, user_id)
        
        if attempt.status != AttemptStatus.ACTIVE:
            raise AppError(
                code=ErrorCode.STATE_CONFLICT,
                message="Попытка уже сдана",
                status_code=409,
                details={"currentState": attempt.status.value},
            )
        
        if attempt.version != expected_version:
            raise AppError(
                code=ErrorCode.VERSION_CONFLICT,
                message="Версия попытки устарела",
                status_code=409,
                details={"currentVersion": attempt.version},
            )
        
        # Upsert ответа
        answers = list(attempt.answers or [])
        existing_idx = next((i for i, a in enumerate(answers)
                            if a["questionId"] == question_id), None)
        new_answer = {
            "questionId": question_id,
            "type": data["type"],
            "value": data["value"],
            "savedAt": datetime.now(timezone.utc).isoformat(),
        }
        if existing_idx is not None:
            answers[existing_idx] = new_answer
        else:
            answers.append(new_answer)
        
        attempt.answers = answers
        attempt.version += 1
        await self.db.commit()
        
        return {
            "answer": new_answer,
            "attemptVersion": attempt.version,
            "serverSavedAt": new_answer["savedAt"],
        }
    
    async def submit(self, attempt_id: uuid.UUID, user_id: uuid.UUID,
                     expected_version: int) -> dict:
        """FN-EXAM-SUBMIT — синхронная оценка для MVP"""
        attempt = await self._get_owned_attempt(attempt_id, user_id)
        
        if attempt.status != AttemptStatus.ACTIVE:
            raise AppError(ErrorCode.STATE_CONFLICT, "Попытка уже сдана", 409)
        
        if attempt.version != expected_version:
            raise AppError(ErrorCode.VERSION_CONFLICT, "Версия устарела", 409)
        
        attempt.status = AttemptStatus.SUBMITTED
        attempt.submitted_at = datetime.now(timezone.utc)
        await self.db.commit()
        
        # Оценивание
        await self._evaluate_attempt(attempt)
        
        return {
            "id": str(attempt.id),
            "status": attempt.status.value,
            "scorePercent": attempt.score_percent,
            "passingPercent": settings.EXAM_PASSING_PERCENT,
        }
    
    async def get_result(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """FN-EXAM-RESULT"""
        attempt = await self._get_owned_attempt(attempt_id, user_id)
        exam_result = await self.db.execute(
            select(Exam).where(Exam.id == attempt.exam_id)
        )
        exam = exam_result.scalar_one()
        
        return {
            "id": str(attempt.id),
            "status": attempt.status.value,
            "scorePercent": attempt.score_percent,
            "passingPercent": exam.passing_percent,
            "feedback": attempt.feedback,
            "reviewItems": (attempt.feedback or {}).get("reviewItems", []),
            "nextAction": self._next_action(attempt),
        }
    
    # === Внутренние ===
    
    async def _evaluate_attempt(self, attempt: ExamAttempt) -> None:
        """FN-EXAM-EVALUATE"""
        attempt.status = AttemptStatus.EVALUATING
        await self.db.commit()
        
        exam_result = await self.db.execute(
            select(Exam).where(Exam.id == attempt.exam_id)
        )
        exam = exam_result.scalar_one()
        questions = exam.questions_snapshot or []
        answers_map = {a["questionId"]: a for a in (attempt.answers or [])}
        
        total = max(len(questions), 1)
        correct = 0
        
        for q in questions:
            ans = answers_map.get(q["id"])
            if not ans:
                continue
            if q["type"] in ("single", "multiple"):
                if ans["value"] == q.get("correctAnswer"):
                    correct += 1
            elif q["type"] == "text":
                # AI оценка свободного ответа
                result = await self.ai.evaluate_free_text(
                    question=q.get("text", ""),
                    answer=str(ans["value"]),
                    rubric=q.get("rubric", {}),
                )
                if result.get("score", 0) >= 0.7:
                    correct += 1
        
        score = (correct / total) * 100
        attempt.score_percent = score
        
        if score >= settings.EXAM_PASSING_PERCENT:
            attempt.status = AttemptStatus.PASSED
            attempt.feedback = {
                "summary": "Экзамен сдан успешно",
                "strengths": [],
                "gaps": [],
                "recommendedTopicIds": [],
                "reviewItems": [],
            }
            await self.db.commit()
            # Открываем следующий этап
            await self._unlock_next(attempt, exam)
        else:
            attempt.status = AttemptStatus.FAILED
            attempt.feedback = {
                "summary": f"Результат {score:.1f}% ниже проходного",
                "strengths": [],
                "gaps": ["Требуется повторить материал"],
                "recommendedTopicIds": [],
                "reviewItems": [],
            }
            await self.db.commit()
        
        attempt.evaluated_at = datetime.now(timezone.utc)
        await self.db.commit()
    
    async def _unlock_next(self, attempt: ExamAttempt, exam: Exam) -> None:
        """FN-EXAM-UNLOCK-NEXT"""
        # Тема → passed
        topic_result = await self.db.execute(
            select(Topic).where(Topic.id == exam.topic_id)
        )
        topic = topic_result.scalar_one()
        topic.status = TopicStatus.PASSED
        
        # Следующая тема locked → available
        next_result = await self.db.execute(
            select(Topic).where(
                Topic.track_id == exam.track_id,
                Topic.order > topic.order,
                Topic.status == TopicStatus.LOCKED,
            ).order_by(Topic.order).limit(1)
        )
        next_topic = next_result.scalar_one_or_none()
        if next_topic:
            next_topic.status = TopicStatus.AVAILABLE
        
        # Если финальный — трек completed
        if exam.final:
            track_result = await self.db.execute(
                select(LearningTrack).where(LearningTrack.id == exam.track_id)
            )
            track = track_result.scalar_one()
            track.status = TrackStatus.COMPLETED
        
        await self.db.commit()
    
    async def _get_owned_exam(self, exam_id: uuid.UUID, user_id: uuid.UUID) -> Exam:
        from src.models.learning import LearningGoal
        result = await self.db.execute(
            select(Exam)
            .join(LearningTrack, Exam.track_id == LearningTrack.id)
            .join(LearningGoal, LearningTrack.goal_id == LearningGoal.id)
            .where(Exam.id == exam_id, LearningGoal.user_id == user_id)
        )
        exam = result.scalar_one_or_none()
        if not exam:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Экзамен не найден", 404)
        return exam
    
    async def _get_owned_attempt(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> ExamAttempt:
        from src.models.learning import LearningGoal
        result = await self.db.execute(
            select(ExamAttempt)
            .join(Exam, ExamAttempt.exam_id == Exam.id)
            .join(LearningTrack, Exam.track_id == LearningTrack.id)
            .join(LearningGoal, LearningTrack.goal_id == LearningGoal.id)
            .where(ExamAttempt.id == attempt_id, LearningGoal.user_id == user_id)
        )
        attempt = result.scalar_one_or_none()
        if not attempt:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Попытка не найдена", 404)
        return attempt
    
    def _serialize_attempt_for_client(self, attempt: ExamAttempt, exam: Exam) -> dict:
        # Вопросы без правильных ответов
        questions = []
        for q in (exam.questions_snapshot or []):
            questions.append({
                "id": q["id"],
                "type": q["type"],
                "text": q.get("text", ""),
                "options": q.get("options", []),
            })
        return {
            "attempt": {
                "id": str(attempt.id),
                "examId": str(exam.id),
                "status": attempt.status.value,
                "version": attempt.version,
            },
            "questions": questions,
            "answers": attempt.answers or [],
            "savePolicy": {"autosave": True, "versionCheck": True},
        }
    
    def _next_action(self, attempt: ExamAttempt) -> str:
        if attempt.status == AttemptStatus.PASSED:
            return "next_topic"
        if attempt.status == AttemptStatus.FAILED:
            return "retry_exam"
        return "wait"