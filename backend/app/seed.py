from sqlalchemy import text

from app.auth import hash_password

# 開発用のアカウント。SEED_SAMPLE_USERS=true のとき起動時に作成する
SAMPLE_USERS = [
    {"login_id": "admin", "name": "管理者", "password": "admin-password", "role": "admin", "task_points": 0},
    {"login_id": "alice", "name": "Alice", "password": "alice-password", "task_points": 3},
    {"login_id": "bob", "name": "Bob", "password": "bob-password", "task_points": 1},
    {"login_id": "carol", "name": "Carol", "password": "carol-password", "task_points": 0},
]


def seed_sample_users(conn):
    """サンプルユーザーがまだなければ作成する。既存の行は変更しない"""
    for user in SAMPLE_USERS:
        conn.execute(
            text(
                "INSERT INTO users (login_id, name, password_hash, role, task_points) "
                "VALUES (:login_id, :name, :password_hash, :role, :task_points) "
                "ON CONFLICT (login_id) DO NOTHING"
            ),
            {
                "login_id": user["login_id"],
                "name": user["name"],
                "password_hash": hash_password(user["password"]),
                "role": user.get("role", "user"),
                "task_points": user["task_points"],
            },
        )
