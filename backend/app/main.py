import logging
import os
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app import auth
from app.seed import seed_sample_users

engine = create_engine(os.environ["DATABASE_URL"])
# Uvicorn と同じ形式でターミナルに出すため、Uvicorn のロガーを使う
logger = logging.getLogger("uvicorn.error")


def check_schema(conn):
    """古い init.sql で作られたデータベースなら、分かりやすいメッセージで止める"""
    has_sessions = conn.execute(text("SELECT to_regclass('sessions') IS NOT NULL")).scalar()
    has_role = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='role')")).scalar()
    if not has_sessions or not has_role:
        raise RuntimeError(
            "データベースのスキーマが古いです。`make reset` でデータを削除してから、"
            "もう一度 `make up` を実行してください（データベースのデータはすべて削除されます）"
        )


@asynccontextmanager
async def lifespan(app):
    with engine.connect() as conn:
        check_schema(conn)
    if os.environ.get("SEED_SAMPLE_USERS") == "true":
        with engine.begin() as conn:
            seed_sample_users(conn)

    # Uvicorn が表示する 0.0.0.0 はコンテナ内の待ち受けアドレスなので、
    # ブラウザーで開くべき URL を別に案内する
    url = os.environ.get("APP_URL", "http://127.0.0.1:8000")
    line = "=" * 60
    logger.info(f"{line}\n  起動しました。ブラウザーで次の URL を開いてください:\n    {url}\n{line}")
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/users")
def list_users(session: str | None = Cookie(default=None)):
    require_user(session)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, login_id, name, task_points FROM users ORDER BY id"))
        return [dict(row._mapping) for row in rows]


def require_user(session):
    with engine.connect() as conn:
        user = auth.get_session_user(conn, session)
    if user is None:
        raise HTTPException(status_code=401, detail="ログインしていません")
    return user


def require_admin(session):
    user = require_user(session)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return user


class UserCreate(BaseModel):
    login_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)


@app.post("/api/users", status_code=201)
def create_user(body: UserCreate, session: str | None = Cookie(default=None)):
    require_admin(session)
    login_id, name = body.login_id.strip(), body.name.strip()
    if not login_id or not name:
        raise HTTPException(status_code=422, detail="ユーザーIDと名前を入力してください")
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("INSERT INTO users (login_id, name, password_hash) VALUES (:login_id, :name, :password_hash) RETURNING id, login_id, name, task_points"),
                {"login_id": login_id, "name": name, "password_hash": auth.hash_password(body.password)},
            ).first()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="そのユーザーIDはすでに使われています")
    return dict(row._mapping)


@app.delete("/api/users/{user_id}", status_code=204)
def delete_user(user_id: int, session: str | None = Cookie(default=None)):
    admin = require_admin(session)
    try:
        with engine.begin() as conn:
            target = conn.execute(text("SELECT role FROM users WHERE id=:id"), {"id": user_id}).first()
            if target is None:
                raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
            if user_id == admin.id:
                raise HTTPException(status_code=400, detail="自分自身は削除できません")
            if target.role == "admin":
                count = conn.execute(text("SELECT count(*) FROM users WHERE role='admin'")).scalar_one()
                if count <= 1:
                    raise HTTPException(status_code=400, detail="最後の管理者は削除できません")
            conn.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})
    except IntegrityError:
        raise HTTPException(status_code=409, detail="割り当てなどの履歴があるため削除できません")


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    points: int = Field(ge=0, le=100000)


@app.get("/api/tasks")
def list_tasks(session: str | None = Cookie(default=None)):
    require_user(session)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, name, points FROM task_type ORDER BY id"))
        return [dict(row._mapping) for row in rows]


@app.post("/api/tasks", status_code=201)
def create_task(body: TaskCreate, session: str | None = Cookie(default=None)):
    require_admin(session)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="任務名を入力してください")
    with engine.begin() as conn:
        row = conn.execute(text("INSERT INTO task_type (name, points) VALUES (:name, :points) RETURNING id, name, points"), {"name": name, "points": body.points}).first()
    return dict(row._mapping)


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, session: str | None = Cookie(default=None)):
    require_admin(session)
    try:
        with engine.begin() as conn:
            if conn.execute(text("SELECT 1 FROM task_type WHERE id=:id"), {"id": task_id}).first() is None:
                raise HTTPException(status_code=404, detail="任務が見つかりません")
            conn.execute(text("DELETE FROM task_type WHERE id=:id"), {"id": task_id})
    except IntegrityError:
        raise HTTPException(status_code=409, detail="割り当てに使われている任務は削除できません")


class LoginRequest(BaseModel):
    login_id: str
    password: str


@app.post("/api/login")
def login(body: LoginRequest, response: Response):
    with engine.begin() as conn:
        user = auth.authenticate(conn, body.login_id, body.password)
        if user is None:
            raise HTTPException(status_code=401, detail="ユーザーIDまたはパスワードが違います")
        token = auth.create_session(conn, user.id)

    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        max_age=int(auth.SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        # HTTPS で公開するときは COOKIE_SECURE=true にする
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
