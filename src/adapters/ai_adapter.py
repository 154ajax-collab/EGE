from abc import ABC, abstractmethod
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()


class AIAdapter(ABC):
    """Интерфейс AI-адаптера (раздел 8 ТЗ)"""
    
    @abstractmethod
    async def evaluate_deadline(
        self, skill: str, target_outcome: str, current_level: str,
        target_date: str, hours_per_week: float,
    ) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def generate_plan(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def propose_plan_change(
        self, plan: Dict[str, Any], text: str,
    ) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def evaluate_free_text(
        self, question: str, answer: str, rubric: Dict[str, Any],
    ) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def tutor_response(
        self, context: Dict[str, Any], user_message: str,
    ) -> Dict[str, Any]:
        pass


class MockAIAdapter(AIAdapter):
    """Mock для разработки (раздел 12 ТЗ)"""
    
    async def evaluate_deadline(self, skill, target_outcome, current_level,
                                target_date, hours_per_week):
        from datetime import datetime, timezone
        target = datetime.fromisoformat(target_date).replace(tzinfo=timezone.utc)
        weeks = max(1, (target - datetime.now(timezone.utc)).days // 7)
        required_weeks = max(4, 100 / max(hours_per_week, 1))
        
        if weeks < required_weeks * 0.5:
            risk = "high"
        elif weeks < required_weeks:
            risk = "medium"
        else:
            risk = "low"
        
        return {
            "risk": risk,
            "estimatedMinWeeks": int(required_weeks * 0.8),
            "estimatedMaxWeeks": int(required_weeks * 1.5),
            "reasons": [f"Для освоения навыка требуется ~{int(required_weeks)} недель"],
            "options": [
                {"type": "extend_deadline", "description": "Увеличить срок"},
                {"type": "increase_hours", "description": "Увеличить нагрузку"},
                {"type": "narrow_goal", "description": "Сузить цель"},
            ],
            "assumptions": ["Средний темп обучения", "Регулярные занятия"],
        }
    
    async def generate_plan(self, brief):
        skill = brief.get("skill", "Навык")
        return {
            "assumptions": ["Программа рассчитана на новичка"],
            "gaps": [
                {
                    "id": "gap-1",
                    "type": "missing_source",
                    "topicId": None,
                    "message": "Не найдены проверенные источники по теме 2",
                    "severity": "warning",
                    "acknowledged": False,
                }
            ],
            "topics": [
                {
                    "id": "topic-1",
                    "title": f"Введение в {skill}",
                    "outcome": "Базовое понимание",
                    "order": 1,
                    "prerequisiteTopicIds": [],
                    "materials": [
                        {
                            "title": f"Введение в {skill}",
                            "type": "article",
                            "url": "https://example.com/intro",
                            "domain": "example.com",
                            "sourceName": "Example",
                            "language": "ru",
                            "required": True,
                        }
                    ],
                },
                {
                    "id": "topic-2",
                    "title": f"Практика {skill}",
                    "outcome": "Применение навыка",
                    "order": 2,
                    "prerequisiteTopicIds": ["topic-1"],
                    "materials": [],
                },
            ],
        }
    
    async def propose_plan_change(self, plan, text):
        return {
            "summary": f"Изменение по запросу: {text[:50]}",
            "impact": "Добавление новой темы",
            "changes": [
                {"action": "add_topic", "topic": {"title": "Новая тема", "order": 99}}
            ],
        }
    
    async def evaluate_free_text(self, question, answer, rubric):
        return {
            "score": 0.75,
            "criterionResults": [],
            "feedback": {
                "summary": "Ответ в целом верный",
                "strengths": ["Понимание основ"],
                "gaps": ["Недостаточная детализация"],
                "recommendedTopicIds": [],
            },
        }
    
    async def tutor_response(self, context, user_message):
        return {
            "content": f"Объяснение по вашему вопросу: {user_message[:100]}...",
            "references": [],
        }


def get_ai_adapter() -> AIAdapter:
    return MockAIAdapter()