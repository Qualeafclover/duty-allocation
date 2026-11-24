import uuid

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from test_access import api
from test_login import log_in

# 行は削除できないので、実行のたびに新しい名前を使う（テストのデータは残ってよい）
PASSWORD = "e2e-password"


def unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def open_admin(driver):
    log_in(driver, "admin", "admin-password")
    # 一覧は操作のたびに描き直されるので、古くなった行を読んだときはやり直す
    wait = WebDriverWait(driver, 10, ignored_exceptions=[StaleElementReferenceException])
    wait.until(EC.url_contains("/admin.html"))
    return wait


def show_page(driver, wait, page):
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'.nav-item[data-page="{page}"]'))).click()


def set_show_inactive(driver, page, checked):
    """「無効も表示」のチェックを切り替える（page は "users" か "tasks"）"""
    checkbox = driver.find_element(By.ID, f"{page[:-1]}ShowInactive")
    if checkbox.is_selected() != checked:
        checkbox.click()


def table_row(driver, table_id, text):
    for row in driver.find_elements(By.CSS_SELECTOR, f"#{table_id} tr"):
        if text in row.text:
            return row
    return None


def wait_for_row(driver, wait, table_id, text):
    wait.until(lambda d: table_row(d, table_id, text) is not None)
    return table_row(driver, table_id, text)


def row_is_active(row):
    """状態バッジで判定する（行の文字にはボタンの「有効にする」なども含まれるため）"""
    return "inactive" not in row.find_element(By.CLASS_NAME, "status-badge").get_attribute("class")


def wait_for_db(wait, db, query, params, expected):
    """画面の操作は非同期なので、データベースの値が期待どおりになるまで待つ"""
    def check(_):
        row = db.execute(query, params).fetchone()
        return row is not None and all(row[key] == value for key, value in expected.items())
    wait.until(check, message=f"DB が {expected} になりませんでした: {params}")


def user_in_db(wait, db, login_id, **expected):
    wait_for_db(wait, db, "SELECT * FROM users WHERE login_id = %s", (login_id,), expected)


def task_in_db(wait, db, name, **expected):
    wait_for_db(wait, db, "SELECT * FROM task_type WHERE name = %s", (name,), expected)


def add_user(driver, wait, login_id, name):
    show_page(driver, wait, "users")
    driver.find_element(By.ID, "addUserBtn").click()
    driver.find_element(By.ID, "field-name").send_keys(name)
    driver.find_element(By.ID, "field-login_id").send_keys(login_id)
    driver.find_element(By.ID, "field-password").send_keys(PASSWORD)
    driver.find_element(By.ID, "saveModal").click()
    wait_for_row(driver, wait, "userTableBody", login_id)


def add_task(driver, wait, name, points):
    show_page(driver, wait, "tasks")
    driver.find_element(By.ID, "addTaskBtn").click()
    driver.find_element(By.ID, "field-name").send_keys(name)
    points_input = driver.find_element(By.ID, "field-points")
    points_input.clear()
    points_input.send_keys(str(points))
    driver.find_element(By.ID, "saveModal").click()
    wait_for_row(driver, wait, "taskTableBody", name)


def set_active(driver, wait, page, text, active):
    """一覧の行の「有効にする」「無効にする」を押す。無効の行も探せるよう「無効も表示」をオンにする"""
    table_id = f"{page[:-1]}TableBody"
    show_page(driver, wait, page)
    set_show_inactive(driver, page, True)
    button_class = "activate-btn" if active else "deactivate-btn"
    wait_for_row(driver, wait, table_id, text).find_element(By.CLASS_NAME, button_class).click()
    if not active:
        driver.switch_to.alert.accept()  # 無効にするときだけ確認ダイアログが出る
    wait.until(lambda d: row_is_active(table_row(d, table_id, text)) == active)


def log_out(driver, wait):
    driver.find_element(By.ID, "logoutButton").click()
    wait.until(EC.presence_of_element_located((By.ID, "login-form")))


def test_admin_cannot_deactivate_self(driver):
    wait = open_admin(driver)
    show_page(driver, wait, "users")
    row = wait_for_row(driver, wait, "userTableBody", "admin")
    assert row.find_elements(By.TAG_NAME, "button") == []


def test_added_user_is_saved_with_hashed_password(driver, db):
    login_id = unique("e2e-user")
    wait = open_admin(driver)
    add_user(driver, wait, login_id, "E2E ユーザー")

    user_in_db(wait, db, login_id, name="E2E ユーザー", role="user", is_active=True)
    password_hash = db.execute(
        "SELECT password_hash FROM users WHERE login_id = %s", (login_id,)
    ).fetchone()["password_hash"]
    assert password_hash.startswith("$argon2")
    assert PASSWORD not in password_hash


def test_user_deactivate_and_reactivate(driver, db):
    login_id = unique("e2e-user")
    wait = open_admin(driver)
    add_user(driver, wait, login_id, "E2E 切り替え")

    set_active(driver, wait, "users", login_id, active=False)
    user_in_db(wait, db, login_id, is_active=False)
    # 無効のユーザーは、「無効も表示」をオフにすると一覧から消える
    set_show_inactive(driver, "users", False)
    wait.until(lambda d: table_row(d, "userTableBody", login_id) is None)

    # 無効のあいだはログインできない
    log_out(driver, wait)
    log_in(driver, login_id, PASSWORD)
    wait.until(EC.text_to_be_present_in_element((By.ID, "error"), "無効"))
    assert "/home.html" not in driver.current_url

    # 有効に戻すとログインできる
    open_admin(driver)
    set_active(driver, wait, "users", login_id, active=True)
    user_in_db(wait, db, login_id, is_active=True)
    log_out(driver, wait)
    log_in(driver, login_id, PASSWORD)
    wait.until(EC.url_contains("/home.html"))


def test_task_add_deactivate_and_reactivate(driver, db):
    name = unique("E2E 任務")
    wait = open_admin(driver)
    add_task(driver, wait, name, 5)
    task_in_db(wait, db, name, points=5, is_active=True)

    set_active(driver, wait, "tasks", name, active=False)
    task_in_db(wait, db, name, is_active=False)

    set_active(driver, wait, "tasks", name, active=True)
    task_in_db(wait, db, name, is_active=True)


def test_mixed_users_and_tasks_change_only_the_right_rows(driver, db):
    """ユーザーと任務を交互に操作し、押した行だけが変わることを確かめる"""
    user_a, user_b = unique("e2e-a"), unique("e2e-b")
    task_a, task_b = unique("E2E 任務A"), unique("E2E 任務B")
    wait = open_admin(driver)

    add_user(driver, wait, user_a, "E2E A")
    add_task(driver, wait, task_a, 2)
    add_user(driver, wait, user_b, "E2E B")
    add_task(driver, wait, task_b, 3)

    set_active(driver, wait, "users", user_a, active=False)
    set_active(driver, wait, "tasks", task_b, active=False)
    user_in_db(wait, db, user_a, is_active=False)
    user_in_db(wait, db, user_b, is_active=True)
    task_in_db(wait, db, task_a, points=2, is_active=True)
    task_in_db(wait, db, task_b, points=3, is_active=False)

    set_active(driver, wait, "users", user_a, active=True)
    set_active(driver, wait, "users", user_b, active=False)
    set_active(driver, wait, "tasks", task_a, active=False)
    user_in_db(wait, db, user_a, is_active=True)
    user_in_db(wait, db, user_b, is_active=False)
    task_in_db(wait, db, task_a, is_active=False)
    task_in_db(wait, db, task_b, is_active=False)

    # 読み込み直しても、データベースと同じ状態が表示される
    driver.refresh()
    wait.until(EC.url_contains("/admin.html"))
    show_page(driver, wait, "users")
    set_show_inactive(driver, "users", True)
    assert row_is_active(wait_for_row(driver, wait, "userTableBody", user_a))
    assert not row_is_active(wait_for_row(driver, wait, "userTableBody", user_b))
    show_page(driver, wait, "tasks")
    set_show_inactive(driver, "tasks", True)
    assert not row_is_active(wait_for_row(driver, wait, "taskTableBody", task_a))
    assert not row_is_active(wait_for_row(driver, wait, "taskTableBody", task_b))


# --- 入力エラー ---
# ブラウザーの入力チェック（minlength など）と、それを通さずに API を呼んだときのサーバーのチェックの両方を確かめる


def open_user_form(driver, wait, login_id, name, password):
    show_page(driver, wait, "users")
    driver.find_element(By.ID, "addUserBtn").click()
    driver.find_element(By.ID, "field-name").send_keys(name)
    driver.find_element(By.ID, "field-login_id").send_keys(login_id)
    driver.find_element(By.ID, "field-password").send_keys(password)
    driver.find_element(By.ID, "saveModal").click()


def open_task_form(driver, wait, name, points):
    show_page(driver, wait, "tasks")
    driver.find_element(By.ID, "addTaskBtn").click()
    driver.find_element(By.ID, "field-name").send_keys(name)
    points_input = driver.find_element(By.ID, "field-points")
    points_input.clear()
    points_input.send_keys(str(points))
    driver.find_element(By.ID, "saveModal").click()


def modal_is_open(driver):
    return "hidden" not in driver.find_element(By.ID, "modalBackdrop").get_attribute("class")


def field_is_invalid(driver, field_id):
    return not driver.execute_script("return arguments[0].checkValidity()", driver.find_element(By.ID, field_id))


def test_duplicate_user_id_shows_error(driver, db):
    wait = open_admin(driver)
    open_user_form(driver, wait, "alice", "別のアリス", PASSWORD)

    wait.until(EC.text_to_be_present_in_element((By.ID, "formError"), "すでに使われています"))
    assert modal_is_open(driver)
    rows = db.execute("SELECT name FROM users WHERE login_id = 'alice'").fetchall()
    assert rows == [{"name": "Alice"}]  # 元のユーザーは上書きされない


def test_short_password_is_rejected(driver, db):
    login_id = unique("e2e-short")
    wait = open_admin(driver)
    open_user_form(driver, wait, login_id, "短いパスワード", "1234567")  # 7 文字

    assert modal_is_open(driver)
    assert field_is_invalid(driver, "field-password")
    # 画面のチェックを通さずに送っても、サーバーが断る
    assert api(driver, "POST", "/api/users",
               {"login_id": login_id, "name": "短いパスワード", "password": "1234567"}) == 422
    assert db.execute("SELECT 1 FROM users WHERE login_id = %s", (login_id,)).fetchone() is None


def test_task_points_must_be_positive(driver, db):
    name = unique("E2E 0点")
    wait = open_admin(driver)
    open_task_form(driver, wait, name, 0)

    assert modal_is_open(driver)
    assert field_is_invalid(driver, "field-points")
    for points in (0, -5):
        assert api(driver, "POST", "/api/tasks", {"name": name, "points": points}) == 422
    assert db.execute("SELECT 1 FROM task_type WHERE name = %s", (name,)).fetchone() is None


def test_blank_names_are_rejected_by_the_server(driver, db):
    """空白だけの名前は、ブラウザーの required では防げないのでサーバーが断る"""
    login_id = unique("e2e-blank")
    open_admin(driver)
    assert api(driver, "POST", "/api/users", {"login_id": login_id, "name": "   ", "password": PASSWORD}) == 422
    assert api(driver, "POST", "/api/tasks", {"name": "   ", "points": 1}) == 422
    assert db.execute("SELECT 1 FROM users WHERE login_id = %s", (login_id,)).fetchone() is None
