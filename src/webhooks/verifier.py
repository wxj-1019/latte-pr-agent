import hmac
import hashlib


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
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def verify_gitlab(token: str, secret: str) -> bool:
        """GitLab: Secret Token 比对"""
        if not token or not secret:
            return False
        return hmac.compare_digest(token, secret)
