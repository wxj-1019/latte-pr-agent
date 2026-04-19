import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_SECRET_KEY_PATH = ".secret_key"


def _get_or_create_key() -> bytes:
    if os.path.exists(_SECRET_KEY_PATH):
        with open(_SECRET_KEY_PATH, "rb") as f:
            key = f.read().strip()
            if key:
                return key

    key = Fernet.generate_key()
    with open(_SECRET_KEY_PATH, "wb") as f:
        f.write(key)
    # Restrict key file access (Unix only; Windows ignores this gracefully)
    try:
        os.chmod(_SECRET_KEY_PATH, 0o600)
    except (OSError, NotImplementedError):
        pass
    logger.info("Generated new encryption key at %s", _SECRET_KEY_PATH)
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
