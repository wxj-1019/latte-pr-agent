import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Allow overriding via environment variable for containerized deployments
_SECRET_KEY_PATH = os.environ.get("SECRET_KEY_PATH", ".secret_key")


def _get_or_create_key() -> bytes:
    # 1. Try env var (best for containers)
    env_key = os.environ.get("LATTE_SECRET_KEY", "")
    if env_key:
        try:
            key = env_key.encode("utf-8")
            # Validate it's a valid Fernet key
            Fernet(key)
            return key
        except Exception:
            logger.warning("LATTE_SECRET_KEY env var is not a valid Fernet key, ignoring")

    # 2. Try file path
    if os.path.exists(_SECRET_KEY_PATH):
        try:
            with open(_SECRET_KEY_PATH, "rb") as f:
                key = f.read().strip()
                if key:
                    # Validate
                    Fernet(key)
                    return key
        except Exception as exc:
            logger.warning("Failed to read secret key from %s: %s", _SECRET_KEY_PATH, exc)

    # 3. Generate new key (with graceful fallback if filesystem is read-only)
    key = Fernet.generate_key()
    try:
        with open(_SECRET_KEY_PATH, "wb") as f:
            f.write(key)
        # Restrict key file access (Unix only; Windows ignores this gracefully)
        try:
            os.chmod(_SECRET_KEY_PATH, 0o600)
        except (OSError, NotImplementedError):
            pass
        logger.info("Generated new encryption key at %s", _SECRET_KEY_PATH)
    except OSError as exc:
        logger.warning(
            "Cannot write secret key to %s (%s). "
            "Encryption will work for this process lifetime, "
            "but persistent encryption requires a writable path or LATTE_SECRET_KEY env var.",
            _SECRET_KEY_PATH, exc
        )
    return key


_fernet = Fernet(_get_or_create_key())


def encrypt_value(plain: str) -> str:
    if not plain:
        return ""
    return _fernet.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_value(cipher: str) -> str | None:
    if not cipher:
        return None
    try:
        return _fernet.decrypt(cipher.encode("utf-8")).decode("utf-8")
    except Exception:
        logger.warning("Failed to decrypt value, returning None")
        return None
