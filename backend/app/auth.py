import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from .config import SESSION_TTL_HOURS
from .db import now, session

SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return secrets.compare_digest(candidate, password_hash)


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(email.strip()))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    with session() as conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash(token), user_id, now(), expires.isoformat(timespec="seconds")),
        )
    return token


def resolve_session(token: str | None) -> dict | None:
    if not token:
        return None
    with session() as conn:
        row = conn.execute(
            """SELECT u.* FROM sessions s
               JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.expires_at > ?""",
            (token_hash(token), now()),
        ).fetchone()
    return dict(row) if row else None


def destroy_session(token: str | None) -> None:
    if not token:
        return
    with session() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
