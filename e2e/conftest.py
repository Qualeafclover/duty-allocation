import os
import uuid
from pathlib import Path

import psycopg
import pytest
from argon2 import PasswordHasher
from psycopg.rows import dict_row
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

DOWNLOADS = Path(__file__).parent.parent / "downloads"
CHROME = DOWNLOADS / "chrome-linux64" / "chrome"
CHROMEDRIVER = DOWNLOADS / "chromedriver-linux64" / "chromedriver"
# docker-compose.yml で公開しているデータベース（make up で起動しておく）
DATABASE_URL = os.environ.get(
    "E2E_DATABASE_URL", "postgresql://duty:password@127.0.0.1:5432/duty"
)


def pytest_addoption(parser):
    parser.addoption(
        "--headed",
        action="store_true",
        help="Show the Chrome window instead of running headless.",
    )


@pytest.fixture
def driver(request):
    if not CHROME.exists() or not CHROMEDRIVER.exists():
        pytest.fail("Chrome not found. Run `make chrome` first.")

    options = webdriver.ChromeOptions()
    options.binary_location = str(CHROME)
    if not request.config.getoption("--headed"):
        options.add_argument("--headless=new")

    driver = webdriver.Chrome(service=Service(str(CHROMEDRIVER)), options=options)
    yield driver
    driver.quit()


@pytest.fixture
def db():
    """画面の操作がデータベースに反映されたかを直接確かめるための接続。
    autocommit にして、アプリが書き込んだ最新の値を毎回読めるようにする"""
    with psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row) as conn:
        yield conn


E2E_PASSWORD = "e2e-password"


@pytest.fixture
def make_user(db):
    """一般ユーザーをデータベースに直接作り、ユーザーIDを返す。
    サンプルユーザーを無効にしたりすると他のテストに影響するので、テストごとに新しく作る"""
    def make():
        login_id = f"e2e-{uuid.uuid4().hex[:8]}"
        db.execute(
            "INSERT INTO users (login_id, name, password_hash) VALUES (%s, %s, %s)",
            (login_id, f"E2E {login_id}", PasswordHasher().hash(E2E_PASSWORD)),
        )
        return login_id
    return make


@pytest.fixture
def make_task(db):
    """任務をデータベースに直接作り、その行を返す"""
    def make(points=1):
        return db.execute(
            "INSERT INTO task_type (name, points) VALUES (%s, %s) RETURNING *",
            (f"E2E 任務-{uuid.uuid4().hex[:8]}", points),
        ).fetchone()
    return make
