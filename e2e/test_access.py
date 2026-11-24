"""ログイン状態と権限のテスト。画面を通さない操作（データベースの直接変更や API の直接呼び出し）にも
サーバーが正しく対応するかを確かめる"""
import hashlib
import uuid

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from conftest import E2E_PASSWORD
from test_login import BASE_URL, log_in


def log_in_as_new_user(driver, make_user):
    login_id = make_user()
    log_in(driver, login_id, E2E_PASSWORD)
    WebDriverWait(driver, 10).until(EC.url_contains("/home.html"))
    return login_id


def session_token_hash(driver):
    """ブラウザーの Cookie のトークンから、sessions テーブルの token_hash を求める"""
    token = driver.get_cookie("session")["value"]
    return hashlib.sha256(token.encode()).hexdigest()


def api(driver, method, path, body=None):
    """ブラウザーのセッションのまま API を直接呼び、ステータスコードを返す（画面のボタンを通さない）"""
    return driver.execute_async_script(
        """
        const [method, path, body, done] = arguments;
        fetch(path, {
            method,
            headers: body ? { "Content-Type": "application/json" } : {},
            body: body ? JSON.stringify(body) : undefined,
        }).then((response) => done(response.status), () => done(-1));
        """,
        method, path, body,
    )


def assert_sent_to_login(driver):
    driver.get(f"{BASE_URL}/home.html")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "login-form")))


def test_expired_session_is_logged_out(driver, db, make_user):
    log_in_as_new_user(driver, make_user)
    # 時計を進める代わりに、このブラウザーのセッションの期限を過去にする
    updated = db.execute(
        "UPDATE sessions SET expires_dt = now() - interval '1 second' WHERE token_hash = %s",
        (session_token_hash(driver),),
    ).rowcount
    assert updated == 1

    assert api(driver, "GET", "/api/me") == 401
    assert_sent_to_login(driver)


def test_deactivating_a_logged_in_user_logs_them_out(driver, db, make_user):
    login_id = log_in_as_new_user(driver, make_user)
    db.execute("UPDATE users SET is_active = false WHERE login_id = %s", (login_id,))

    # 次のリクエストからすぐに使えなくなる（再ログインを待たない）
    assert api(driver, "GET", "/api/me") == 401
    assert_sent_to_login(driver)


def test_regular_user_cannot_call_admin_apis(driver, db, make_user, make_task):
    target_id = make_user()
    target = db.execute("SELECT id FROM users WHERE login_id = %s", (target_id,)).fetchone()
    task = make_task()
    new_login_id = f"e2e-{uuid.uuid4().hex[:8]}"
    new_task_name = f"E2E 任務-{uuid.uuid4().hex[:8]}"
    log_in_as_new_user(driver, make_user)

    statuses = {
        "GET /api/tasks": api(driver, "GET", "/api/tasks"),
        "POST /api/users": api(driver, "POST", "/api/users",
                               {"login_id": new_login_id, "name": "侵入", "password": "password123"}),
        "PATCH /api/users": api(driver, "PATCH", f"/api/users/{target['id']}", {"is_active": False}),
        "POST /api/tasks": api(driver, "POST", "/api/tasks", {"name": new_task_name, "points": 1}),
        "PATCH /api/tasks": api(driver, "PATCH", f"/api/tasks/{task['id']}", {"is_active": False}),
    }
    assert statuses == {key: 403 for key in statuses}

    # データベースも変わっていない
    assert db.execute("SELECT 1 FROM users WHERE login_id = %s", (new_login_id,)).fetchone() is None
    assert db.execute("SELECT is_active FROM users WHERE id = %s", (target["id"],)).fetchone()["is_active"]
    assert db.execute("SELECT 1 FROM task_type WHERE name = %s", (new_task_name,)).fetchone() is None
    assert db.execute("SELECT is_active FROM task_type WHERE id = %s", (task["id"],)).fetchone()["is_active"]


def test_logged_out_browser_cannot_call_apis(driver):
    driver.get(BASE_URL)
    for method, path in [("GET", "/api/me"), ("GET", "/api/users"), ("GET", "/api/tasks")]:
        assert api(driver, method, path) == 401, path


def test_regular_user_is_sent_away_from_admin_page(driver, make_user):
    log_in_as_new_user(driver, make_user)
    driver.get(f"{BASE_URL}/admin.html")
    WebDriverWait(driver, 10).until(EC.url_contains("/home.html"))


def test_admin_is_sent_from_home_to_admin_page(driver):
    log_in(driver, "admin", "admin-password")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.url_contains("/admin.html"))
    driver.get(f"{BASE_URL}/home.html")
    wait.until(EC.url_contains("/admin.html"))


def test_login_removes_expired_sessions(driver, db, make_user):
    # 誰かの期限切れのセッションが残っている状態にする
    other = make_user()
    stale_hash = f"e2e-stale-{uuid.uuid4().hex}"
    db.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_dt) "
        "SELECT %s, id, now() - interval '1 day' FROM users WHERE login_id = %s",
        (stale_hash, other),
    )

    log_in_as_new_user(driver, make_user)

    assert db.execute("SELECT 1 FROM sessions WHERE token_hash = %s", (stale_hash,)).fetchone() is None
    assert db.execute("SELECT count(*) AS n FROM sessions WHERE expires_dt <= now()").fetchone()["n"] == 0
    # 自分の新しいセッションは残っている
    assert db.execute(
        "SELECT 1 FROM sessions WHERE token_hash = %s", (session_token_hash(driver),)
    ).fetchone() is not None
