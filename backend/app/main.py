import logging
import os
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, text

from app import auth
from app.seed import seed_sample_users

engine = create_engine(os.environ["DATABASE_URL"])
# Uvicorn と同じ形式でターミナルに出すため、Uvicorn のロガーを使う
logger = logging.getLogger("uvicorn.error")


def check_schema(conn):
    """古い init.sql で作られたデータベースなら、分かりやすいメッセージで止める"""
    has_sessions = conn.execute(text("SELECT to_regclass('sessions') IS NOT NULL")).scalar()
    if not has_sessions:
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
def list_users():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, name, task_points FROM users ORDER BY id"))
        return [dict(row._mapping) for row in rows]


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
