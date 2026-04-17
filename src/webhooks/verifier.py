import hmac
import hashlib
import logging
import secrets

logger = logging.getLogger(__name__)


class WebhookVerifier:
    """GitHub/GitLab Webhook 签名验证"""

    @staticmethod
    def verify_github(payload: bytes, signature: str, secret: str) -> bool:
        """GitHub: HMAC-SHA256 校验"""
        if not signature or not secret:
            logger.warning("GitHub webhook verification failed: missing signature or secret")
            return False
        expected = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        valid = secrets.compare_digest(expected, signature)
        if not valid:
            logger.warning("GitHub webhook verification failed: signature mismatch")
        return valid

    @staticmethod
    def verify_gitlab(token: str, secret: str) -> bool:
        """GitLab: Secret Token 安全比对（防止时序攻击）"""
        if not token or not secret:
            logger.warning("GitLab webhook verification failed: missing token or secret")
            return False
        valid = secrets.compare_digest(token, secret)
        if not valid:
            logger.warning("GitLab webhook verification failed: token mismatch")
        return valid
