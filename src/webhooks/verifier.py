import hmac
import hashlib
import secrets


class WebhookVerifier:
    """GitHub/GitLab Webhook 签名验证"""

    @staticmethod
    def verify_github(payload: bytes, signature: str, secret: str) -> bool:
        """GitHub: HMAC-SHA256 校验"""
        if not signature or not secret:
            return False
        expected = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return secrets.compare_digest(expected, signature)

    @staticmethod
    def verify_gitlab(token: str, secret: str) -> bool:
        """GitHub: Secret Token 安全比对（防止时序攻击）"""
        if not token or not secret:
            return False
        return secrets.compare_digest(token, secret)
