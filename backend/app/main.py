import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text

app = FastAPI()
engine = create_engine(os.environ["DATABASE_URL"])


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


# Keep this last so it doesn't take over the /api routes
app.mount("/", StaticFiles(directory="../frontend", html=True))
