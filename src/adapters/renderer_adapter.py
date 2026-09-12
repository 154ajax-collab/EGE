from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import uuid
import structlog

logger = structlog.get_logger()


class RendererAdapter(ABC):
    """PNG renderer (раздел 8 ТЗ)"""
    
    @abstractmethod
    async def render_certificate(self, data: Dict[str, Any]) -> str:
        """Возвращает storage key для PNG"""
        pass


class MockRendererAdapter(RendererAdapter):
    """Mock — просто сохраняем запись, не генерируем реальный PNG"""
    
    async def render_certificate(self, data: Dict[str, Any]) -> str:
        key = f"certificates/{data['certificateId']}.png"
        logger.info("MOCK: Rendered certificate", key=key, name=data.get("certificateName"))
        return key


def get_renderer_adapter() -> RendererAdapter:
    return MockRendererAdapter()