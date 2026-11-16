from sqlalchemy import text

from app.auth import hash_password

# Development-only accounts, created on startup when SEED_SAMPLE_USERS=true
SAMPLE_USERS = [
    {"login_id": "alice", "name": "Alice", "password": "alice-password", "task_points": 3},
    {"login_id": "bob", "name": "Bob", "password": "bob-password", "task_points": 1},
    {"login_id": "carol", "name": "Carol", "password": "carol-password", "task_points": 0},
]


def seed_sample_users(conn):
    """Create the sample users if they don't exist yet. Existing rows are left alone."""
    for user in SAMPLE_USERS:
        conn.execute(
            text(
                "INSERT INTO users (login_id, name, password_hash, task_points) "
                "VALUES (:login_id, :name, :password_hash, :task_points) "
                "ON CONFLICT (login_id) DO NOTHING"
            ),
            {
                "login_id": user["login_id"],
                "name": user["name"],
                "password_hash": hash_password(user["password"]),
                "task_points": user["task_points"],
            },
        )
