"""authenticate と get_session_user をデータベースに対して直接確かめる。
E2E では「ログイン画面に戻された」としか分からないので、ここで理由ごとに分けて確かめる"""
import pytest
from sqlalchemy import text

from app.auth import (
    _hash_token,
    authenticate,
    create_session,
    delete_session,
    delete_user_sessions,
    get_session_user,
    hash_password,
)

PASSWORD = "unit-password"


@pytest.fixture
def user_id(conn):
    return conn.execute(
        text(
            "INSERT INTO users (login_id, name, password_hash) "
            "VALUES ('unit-user', 'ユニット', :password_hash) RETURNING id"
        ),
        {"password_hash": hash_password(PASSWORD)},
    ).scalar()


def deactivate(conn, user_id):
    conn.execute(text("UPDATE users SET is_active = false WHERE id = :id"), {"id": user_id})


def expire(conn, token):
    conn.execute(
        text("UPDATE sessions SET expires_dt = now() - interval '1 second' WHERE token_hash = :h"),
        {"h": _hash_token(token)},
    )


# --- authenticate ---

def test_authenticate_correct_password(conn, user_id):
    assert authenticate(conn, "unit-user", PASSWORD).id == user_id


def test_authenticate_wrong_password(conn, user_id):
    assert authenticate(conn, "unit-user", "wrong-password") is None


def test_authenticate_unknown_user(conn):
    assert authenticate(conn, "no-such-user", PASSWORD) is None


def test_authenticate_inactive_user_returns_row_marked_inactive(conn, user_id):
    # パスワードが合えば行を返し、無効かどうかはログイン処理が見て 403 にする
    deactivate(conn, user_id)
    user = authenticate(conn, "unit-user", PASSWORD)
    assert user is not None and user.is_active is False


def test_authenticate_user_without_password_hash(conn):
    conn.execute(text("INSERT INTO users (login_id, name) VALUES ('no-hash', 'ハッシュなし')"))
    assert authenticate(conn, "no-hash", "dummy-password") is None


# --- get_session_user ---

def test_valid_session(conn, user_id):
    token = create_session(conn, user_id)
    user = get_session_user(conn, token)
    assert (user.id, user.login_id, user.role) == (user_id, "unit-user", "user")
    assert user.expires_dt > user.login_dt


def test_session_token_is_stored_only_as_hash(conn, user_id):
    token = create_session(conn, user_id)
    stored = conn.execute(text("SELECT token_hash FROM sessions WHERE user_id = :id"), {"id": user_id}).scalar()
    assert stored == _hash_token(token) and stored != token


@pytest.mark.parametrize("token", [None, "", "unknown-token"])
def test_missing_or_unknown_token(conn, token):
    assert get_session_user(conn, token) is None


def test_expired_session(conn, user_id):
    token = create_session(conn, user_id)
    expire(conn, token)
    assert get_session_user(conn, token) is None


def test_session_of_deactivated_user(conn, user_id):
    token = create_session(conn, user_id)
    deactivate(conn, user_id)
    assert get_session_user(conn, token) is None


def test_logout_deletes_only_that_session(conn, user_id):
    token_a = create_session(conn, user_id)
    token_b = create_session(conn, user_id)
    delete_session(conn, token_a)
    assert get_session_user(conn, token_a) is None
    assert get_session_user(conn, token_b) is not None


def test_delete_user_sessions_logs_out_everywhere(conn, user_id):
    tokens = [create_session(conn, user_id) for _ in range(2)]
    delete_user_sessions(conn, user_id)
    assert all(get_session_user(conn, token) is None for token in tokens)


def test_create_session_removes_expired_sessions(conn, user_id):
    old = create_session(conn, user_id)
    expire(conn, old)
    create_session(conn, user_id)
    remaining = conn.execute(
        text("SELECT count(*) FROM sessions WHERE token_hash = :h"), {"h": _hash_token(old)}
    ).scalar()
    assert remaining == 0
