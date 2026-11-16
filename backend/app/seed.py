from sqlalchemy import text

from app.auth import hash_password

# Development-only accounts, created on startup when SEED_SAMPLE_USERS=true
SAMPLE_USERS = [
    {"login_id": "alice", "name": "Alice", "password": "alice-password", "task_points": 3, "role": "user"},
    {"login_id": "bob", "name": "Bob", "password": "bob-password", "task_points": 1, "role": "user"},
    {"login_id": "carol", "name": "Carol", "password": "carol-password", "task_points": 0, "role": "user"},
    {"login_id": "U001", "name": "山田 太郎", "password": "U001-password", "task_points": 0, "role": "user"},
    {"login_id": "U002", "name": "佐藤 花子", "password": "U002-password", "task_points": 0, "role": "user"},
    {"login_id": "U003", "name": "鈴木 一郎", "password": "U003-password", "task_points": 0, "role": "user"},
    {"login_id": "U004", "name": "高橋 美咲", "password": "U004-password", "task_points": 0, "role": "user"},
    {"login_id": "admin", "name": "管理者", "password": "admin-password", "task_points": 0, "role": "admin"},
]


def seed_sample_users(conn):
    """Create the sample users if they don't exist yet. Existing rows are left alone."""
    for user in SAMPLE_USERS:
        conn.execute(
            text(
                "INSERT INTO users (login_id, name, password_hash, task_points, role) "
                "VALUES (:login_id, :name, :password_hash, :task_points, :role) "
                "ON CONFLICT (login_id) DO NOTHING"
            ),
            {
                "login_id": user["login_id"],
                "name": user["name"],
                "password_hash": hash_password(user["password"]),
                "task_points": user["task_points"],
                "role": user["role"],
            },
        )
