import os
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from app import auth
from app.seed import seed_sample_users

engine = create_engine(os.environ["DATABASE_URL"])


def check_schema(conn):
    """Fail with a clear message if the database was created from an older init.sql."""
    has_sessions = conn.execute(text("SELECT to_regclass('sessions') IS NOT NULL")).scalar()
    if not has_sessions:
        raise RuntimeError(
            "データベースのスキーマが古いです。`make reset` で db/init.sql から作り直してください"
            "（データベースのデータはすべて削除されます）"
        )
    # Add the role column to existing local databases without deleting user data.
    conn.execute(
        text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user'")
    )


@asynccontextmanager
async def lifespan(app):
    with engine.begin() as conn:
        check_schema(conn)
    if os.environ.get("SEED_SAMPLE_USERS") == "true":
        with engine.begin() as conn:
            seed_sample_users(conn)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/users")
def list_users():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, name, task_points FROM users ORDER BY id"))
        return [dict(row._mapping) for row in rows]


def require_admin(conn, session):
    user = auth.get_session_user(conn, session)
    if user is None or user.role != "admin":
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return user


@app.get("/api/admin/users")
def list_admin_users(session: str | None = Cookie(default=None)):
    with engine.connect() as conn:
        require_admin(conn, session)
        rows = conn.execute(
            text("SELECT id, login_id, name FROM users WHERE role = 'user' ORDER BY id")
        )
        return [dict(row._mapping) for row in rows]


class CreateUserRequest(BaseModel):
    login_id: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=8, max_length=128)


@app.post("/api/admin/users", status_code=201)
def create_admin_user(body: CreateUserRequest, session: str | None = Cookie(default=None)):
    login_id = body.login_id.strip()
    name = body.name.strip()
    if not login_id or not name:
        raise HTTPException(status_code=422, detail="ユーザーIDとユーザー名を入力してください")
    with engine.begin() as conn:
        require_admin(conn, session)
        existing = conn.execute(
            text("SELECT 1 FROM users WHERE login_id = :login_id"), {"login_id": login_id}
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="このユーザーIDは既に登録されています")
        row = conn.execute(
            text(
                "INSERT INTO users (login_id, name, password_hash, task_points, role) "
                "VALUES (:login_id, :name, :password_hash, 0, 'user') "
                "RETURNING id, login_id, name"
            ),
            {"login_id": login_id, "name": name, "password_hash": auth.hash_password(body.password)},
        ).first()
        return dict(row._mapping)


@app.delete("/api/admin/users/{user_id}")
def delete_admin_user(user_id: int, session: str | None = Cookie(default=None)):
    with engine.begin() as conn:
        require_admin(conn, session)
        user = conn.execute(
            text("SELECT id, role FROM users WHERE id = :user_id"), {"user_id": user_id}
        ).first()
        if user is None or user.role != "user":
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        in_use = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM assignment WHERE user_id = :user_id) "
                "OR EXISTS (SELECT 1 FROM unavailable WHERE user_id = :user_id)"
            ),
            {"user_id": user_id},
        ).scalar()
        if in_use:
            raise HTTPException(
                status_code=409,
                detail="当番または不在予定に登録されているため削除できません",
            )
        conn.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
        return {"status": "ok"}


class LoginRequest(BaseModel):
    login_id: str
    password: str
    role: str = "user"


@app.post("/api/login")
def login(body: LoginRequest, response: Response):
    if body.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="ログイン種別が正しくありません")
    with engine.begin() as conn:
        user = auth.authenticate(conn, body.login_id, body.password, body.role)
        if user is None:
            raise HTTPException(status_code=401, detail="ユーザーIDまたはパスワードが違います")
        token = auth.create_session(conn, user.id)

    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        max_age=int(auth.SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        # Set COOKIE_SECURE=true when serving over HTTPS
        secure=os.environ.get("COOKIE_SECURE") == "true",
    )
    return {"status": "ok"}


@app.post("/api/logout")
def logout(response: Response, session: str | None = Cookie(default=None)):
    with engine.begin() as conn:
        auth.delete_session(conn, session)
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"status": "ok"}


@app.get("/api/me")
def me(session: str | None = Cookie(default=None)):
    with engine.connect() as conn:
        user = auth.get_session_user(conn, session)
    if user is None:
        raise HTTPException(status_code=401, detail="ログインしていません")
    return dict(user._mapping)


# Keep this last so it doesn't take over the /api routes
app.mount("/", StaticFiles(directory="../frontend", html=True))
