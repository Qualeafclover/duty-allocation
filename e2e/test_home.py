from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def test_home_page_lists_users(driver):
    driver.get("http://localhost:8000")
    WebDriverWait(driver, 10).until(
        EC.text_to_be_present_in_element((By.ID, "users"), "Alice")
    )
