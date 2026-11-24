from sqlalchemy import text

from app import seed
from app.auth import verify_password
from app.seed import SAMPLE_USERS, seed_sample_users


def count_user(conn, login_id):
    return conn.execute(
        text("SELECT count(*) FROM users WHERE login_id = :login_id"), {"login_id": login_id}
    ).scalar()


def test_creates_missing_users_with_hashed_password(conn, monkeypatch):
    # 既存のサンプルユーザーに影響しないよう、テスト用のユーザーだけを作らせる
    monkeypatch.setattr(seed, "SAMPLE_USERS", [
        {"login_id": "seed-test", "name": "シード", "password": "seed-password", "role": "admin", "task_points": 4},
    ])
    seed_sample_users(conn)

    user = conn.execute(text("SELECT * FROM users WHERE login_id = 'seed-test'")).one()
    assert (user.name, user.role, user.task_points, user.is_active) == ("シード", "admin", 4, True)
    assert verify_password(user.password_hash, "seed-password")
    assert "seed-password" not in user.password_hash


def test_role_defaults_to_user(conn, monkeypatch):
    monkeypatch.setattr(seed, "SAMPLE_USERS", [
        {"login_id": "seed-test", "name": "シード", "password": "seed-password", "task_points": 0},
    ])
    seed_sample_users(conn)
    assert conn.execute(text("SELECT role FROM users WHERE login_id = 'seed-test'")).scalar() == "user"


def test_running_twice_does_not_duplicate(conn):
    seed_sample_users(conn)
    seed_sample_users(conn)
    for user in SAMPLE_USERS:
        assert count_user(conn, user["login_id"]) == 1


def test_does_not_overwrite_existing_users(conn):
    # 再起動のたびに、管理者が変えた内容が元に戻ってはいけない
    seed_sample_users(conn)
    before = conn.execute(text("SELECT password_hash FROM users WHERE login_id = 'alice'")).scalar()
    conn.execute(text(
        "UPDATE users SET name = '変更後', task_points = 99, is_active = false WHERE login_id = 'alice'"
    ))

    seed_sample_users(conn)

    alice = conn.execute(text("SELECT * FROM users WHERE login_id = 'alice'")).one()
    assert (alice.name, alice.task_points, alice.is_active) == ("変更後", 99, False)
    assert alice.password_hash == before  # パスワードも作り直されない
