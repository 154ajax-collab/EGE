import ipaddress
from urllib.parse import urlparse
from typing import Dict, Any
from datetime import datetime, timezone
import httpx
import structlog

logger = structlog.get_logger()

# Приватные диапазоны IP (раздел 11 ТЗ - SSRF protection)
FORBIDDEN_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


class SourceChecker:
    """FN-SOURCE-CHECK (раздел 6.3 ТЗ)"""
    
    async def check(self, url: str, expected_type: str = "article") -> Dict[str, Any]:
        # 1. Нормализация
        try:
            parsed = urlparse(url)
        except Exception:
            return self._broken(url, "invalid_url")
        
        # 2. HTTPS only
        if parsed.scheme != "https":
            return self._broken(url, "non_https")
        
        # 3. Проверка hostname
        hostname = parsed.hostname or ""
        if not hostname:
            return self._broken(url, "no_hostname")
        
        # 4. Проверка на приватные IP
        if self._is_private_hostname(hostname):
            return self._broken(url, "private_ip")
        
        # 5. HTTP-проверка с таймаутом
        try:
            async with httpx.AsyncClient(
                timeout=5.0,
                follow_redirects=True,
                max_redirects=3,
            ) as client:
                response = await client.head(url)
                
                # Проверка на редирект в приватную зону
                final_url = str(response.url)
                final_parsed = urlparse(final_url)
                if self._is_private_hostname(final_parsed.hostname or ""):
                    return self._broken(url, "redirect_to_private")
                
                if response.status_code >= 400:
                    return self._broken(url, f"http_{response.status_code}")
                
                title = response.headers.get("title", "")  # обычно нет в HEAD
                return {
                    "status": "verified" if response.status_code < 400 else "broken",
                    "normalizedUrl": final_url,
                    "httpStatus": response.status_code,
                    "title": title,
                    "domain": parsed.hostname,
                    "language": "ru",
                    "type": expected_type,
                    "officialSource": False,
                    "checkedAt": datetime.now(timezone.utc).isoformat(),
                    "failureCode": None,
                }
        except httpx.TimeoutException:
            return self._broken(url, "timeout")
        except Exception as e:
            logger.warning("Source check failed", url=url, error=str(e))
            return self._broken(url, "unreachable")
    
    def _is_private_hostname(self, hostname: str) -> bool:
        if not hostname:
            return True
        if hostname in ("localhost", "127.0.0.1", "::1"):
            return True
        try:
            ip = ipaddress.ip_address(hostname)
            return any(ip in net for net in FORBIDDEN_NETWORKS)
        except ValueError:
            # Это домен, не IP — ок
            return False
    
    def _broken(self, url: str, code: str) -> Dict[str, Any]:
        return {
            "status": "broken",
            "normalizedUrl": url,
            "httpStatus": None,
            "title": None,
            "domain": urlparse(url).hostname,
            "language": None,
            "type": None,
            "officialSource": False,
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "failureCode": code,
        }