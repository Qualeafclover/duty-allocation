from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "http://localhost:8000"


def log_in(driver, login_id, password):
    driver.get(BASE_URL)
    driver.find_element(By.ID, "login-id").send_keys(login_id)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.ID, "login-button").click()


def test_login_shows_home_page(driver):
    log_in(driver, "alice", "alice-password")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.url_contains("/home.html"))
    wait.until(EC.text_to_be_present_in_element((By.ID, "welcome"), "Alice"))
    wait.until(EC.text_to_be_present_in_element((By.ID, "users"), "Bob"))


def test_session_survives_reload(driver):
    log_in(driver, "alice", "alice-password")
    WebDriverWait(driver, 10).until(EC.url_contains("/home.html"))
    driver.get(BASE_URL)  # ログイン済みならログインページからマイページへ戻される
    WebDriverWait(driver, 10).until(EC.url_contains("/home.html"))


def test_wrong_password_shows_error(driver):
    log_in(driver, "alice", "wrong-password")
    WebDriverWait(driver, 10).until(
        EC.text_to_be_present_in_element((By.ID, "error"), "パスワードが違います")
    )
    assert "/home.html" not in driver.current_url


def test_logout_returns_to_login(driver):
    log_in(driver, "alice", "alice-password")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.element_to_be_clickable((By.ID, "logout-button"))).click()
    wait.until(EC.presence_of_element_located((By.ID, "login-form")))
    driver.get(f"{BASE_URL}/home.html")  # セッションが消えたので、ログインページへ戻される
    wait.until(EC.presence_of_element_located((By.ID, "login-form")))


def test_home_page_requires_login(driver):
    driver.get(f"{BASE_URL}/home.html")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "login-form"))
    )
