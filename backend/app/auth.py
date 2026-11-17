import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import text

SESSION_COOKIE = "session"
SESSION_LIFETIME = timedelta(days=7)

_hasher = PasswordHasher()
# 存在しないユーザーIDのときもこのハッシュで照合する。こうすると、ID 違いと
# パスワード違いで応答時間が変わらず、登録済みの ID を推測されない
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


def authenticate(conn, login_id, password):
    """ユーザーIDとパスワードが合えばユーザーの行を、合わなければ None を返す"""
    user = conn.execute(
        text("SELECT id, password_hash FROM users WHERE login_id = :login_id"),
        {"login_id": login_id},
    ).first()
    if not verify_password(user.password_hash if user else None, password):
        return None
    return user


def create_session(conn, user_id):
    """セッションを保存し、ブラウザーに渡すトークンを返す"""
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
    """トークンに対応するログイン中のユーザーを返す。無効か期限切れなら None"""
    if not token:
        return None
    return conn.execute(
        text(
            "SELECT u.id, u.login_id, u.name, u.task_points, "
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
