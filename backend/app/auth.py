import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import text

SESSION_COOKIE = "session"
SESSION_LIFETIME = timedelta(days=7)

_hasher = PasswordHasher()
# Checked against when the login ID doesn't exist, so a wrong ID takes as long
# as a wrong password and response times don't reveal which IDs are registered
_DUMMY_HASH = _hasher.hash("dummy-password")


def hash_password(password):
    return _hasher.hash(password)


def verify_password(password_hash, password):
    try:
        matched = _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return matched and password_hash is not None


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(conn, login_id, password, role="user"):
    """Return the user row if the login ID and password match, else None."""
    user = conn.execute(
        text("SELECT id, password_hash, role FROM users WHERE login_id = :login_id"),
        {"login_id": login_id},
    ).first()
    if not verify_password(user.password_hash if user else None, password):
        return None
    if user.role != role:
        return None
    return user


def create_session(conn, user_id):
    """Store a new session and return the token to give to the browser."""
    token = secrets.token_urlsafe(32)
    conn.execute(
        text(
            "INSERT INTO sessions (token_hash, user_id, expires_dt) "
            "VALUES (:token_hash, :user_id, now() + :lifetime)"
        ),
        {"token_hash": _hash_token(token), "user_id": user_id, "lifetime": SESSION_LIFETIME},
    )
    return token


def get_session_user(conn, token):
    """Return the logged-in user for a session token, or None if it's invalid or expired."""
    if not token:
        return None
    return conn.execute(
        text(
            "SELECT u.id, u.login_id, u.name, u.task_points, u.role, "
            "       s.created_dt AS login_dt, s.expires_dt "
            "FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = :token_hash AND s.expires_dt > now()"
        ),
        {"token_hash": _hash_token(token)},
    ).first()


def delete_session(conn, token):
    if token:
        conn.execute(
            text("DELETE FROM sessions WHERE token_hash = :token_hash"),
            {"token_hash": _hash_token(token)},
        )
