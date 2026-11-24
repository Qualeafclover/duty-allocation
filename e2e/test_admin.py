import uuid

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from test_login import BASE_URL, log_in


def open_users_page(driver):
    log_in(driver, "admin", "admin-password")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.url_contains("/admin.html"))
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.nav-item[data-page="users"]'))).click()
    return wait


def user_row(driver, login_id):
    for row in driver.find_elements(By.CSS_SELECTOR, "#userTableBody tr"):
        if login_id in row.text:
            return row
    return None


def test_admin_cannot_deactivate_self(driver):
    wait = open_users_page(driver)
    wait.until(lambda d: user_row(d, "admin") is not None)
    assert user_row(driver, "admin").find_elements(By.TAG_NAME, "button") == []


def test_deactivated_user_cannot_log_in(driver):
    # 行は削除できないので、実行のたびに新しいユーザーIDを使う
    login_id = f"e2e-{uuid.uuid4().hex[:8]}"
    password = "e2e-password"

    wait = open_users_page(driver)
    driver.find_element(By.ID, "addUserBtn").click()
    driver.find_element(By.ID, "field-name").send_keys("E2E テスト")
    driver.find_element(By.ID, "field-login_id").send_keys(login_id)
    driver.find_element(By.ID, "field-password").send_keys(password)
    driver.find_element(By.ID, "saveModal").click()
    wait.until(lambda d: user_row(d, login_id) is not None)

    user_row(driver, login_id).find_element(By.CLASS_NAME, "deactivate-btn").click()
    driver.switch_to.alert.accept()
    # 無効のユーザーは、「無効も表示」をオンにするまで一覧に出ない
    wait.until(lambda d: user_row(d, login_id) is None)
    driver.find_element(By.ID, "userShowInactive").click()
    wait.until(lambda d: user_row(d, login_id) is not None)
    assert "無効" in user_row(driver, login_id).text

    driver.find_element(By.ID, "logoutButton").click()
    wait.until(EC.presence_of_element_located((By.ID, "login-form")))
    log_in(driver, login_id, password)
    wait.until(EC.text_to_be_present_in_element((By.ID, "error"), "無効"))
    assert "/home.html" not in driver.current_url
