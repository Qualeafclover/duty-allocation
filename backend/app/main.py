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
    has_columns = conn.execute(
        text(
            "SELECT count(*) = 3 FROM information_schema.columns "
            "WHERE (table_name = 'users' AND column_name IN ('role', 'is_active')) "
            "   OR (table_name = 'task_type' AND column_name = 'is_active')"
        )
    ).scalar()
    if not has_sessions or not has_columns:
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


@app.middleware("http")
async def no_cache(request, call_next):
    """ブラウザーが古い HTML/CSS/JS を使い続けないよう、毎回サーバーに確認させる。
    変更がなければ 304 が返るだけなので、遅くはならない"""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/users")
def list_users(session: str | None = Cookie(default=None)):
    """管理者にはすべてのユーザーを、一般ユーザーには有効な一般ユーザーだけを返す（管理者は含めない）"""
    user = require_user(session)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, login_id, name, role, task_points, is_active FROM users "
                "WHERE :is_admin OR (is_active AND role = 'user') ORDER BY id"
            ),
            {"is_admin": user.role == "admin"},
        )
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
                text("INSERT INTO users (login_id, name, password_hash) VALUES (:login_id, :name, :password_hash) RETURNING id, login_id, name, role, task_points, is_active"),
                {"login_id": login_id, "name": name, "password_hash": auth.hash_password(body.password)},
            ).first()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="そのユーザーIDはすでに使われています")
    return dict(row._mapping)


class ActiveUpdate(BaseModel):
    is_active: bool


# ユーザーと任務は削除せず、有効・無効を切り替える。行を消さないので、
# 割り当てなどの履歴から参照されていても ID がそのまま残る
@app.patch("/api/users/{user_id}")
def set_user_active(user_id: int, body: ActiveUpdate, session: str | None = Cookie(default=None)):
    admin = require_admin(session)
    # 自分を無効にすると、ログインできる管理者がいなくなる場合がある
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="自分自身の状態は変更できません")
    with engine.begin() as conn:
        row = conn.execute(
            text("UPDATE users SET is_active = :is_active WHERE id = :id RETURNING id, login_id, name, role, task_points, is_active"),
            {"id": user_id, "is_active": body.is_active},
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        if not body.is_active:
            # ログイン中なら、その場でログアウトさせる
            auth.delete_user_sessions(conn, user_id)
    return dict(row._mapping)


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    points: int = Field(ge=1, le=100000)  # 任務は 1 ポイント以上


@app.get("/api/tasks")
def list_tasks(session: str | None = Cookie(default=None)):
    """すべての任務を返す。今のところ一般ユーザーは任務を見る必要がないので、管理者だけ"""
    require_admin(session)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, name, points, is_active FROM task_type ORDER BY id"))
        return [dict(row._mapping) for row in rows]


@app.post("/api/tasks", status_code=201)
def create_task(body: TaskCreate, session: str | None = Cookie(default=None)):
    require_admin(session)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="任務名を入力してください")
    with engine.begin() as conn:
        row = conn.execute(text("INSERT INTO task_type (name, points) VALUES (:name, :points) RETURNING id, name, points, is_active"), {"name": name, "points": body.points}).first()
    return dict(row._mapping)


@app.patch("/api/tasks/{task_id}")
def set_task_active(task_id: int, body: ActiveUpdate, session: str | None = Cookie(default=None)):
    require_admin(session)
    with engine.begin() as conn:
        row = conn.execute(
            text("UPDATE task_type SET is_active = :is_active WHERE id = :id RETURNING id, name, points, is_active"),
            {"id": task_id, "is_active": body.is_active},
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="任務が見つかりません")
    return dict(row._mapping)


class LoginRequest(BaseModel):
    login_id: str
    password: str


@app.post("/api/login")
def login(body: LoginRequest, response: Response):
    with engine.begin() as conn:
        user = auth.authenticate(conn, body.login_id, body.password)
        if user is None:
            raise HTTPException(status_code=401, detail="ユーザーIDまたはパスワードが違います")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="このアカウントは無効になっています。管理者に連絡してください")
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
