from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

DOWNLOADS = Path(__file__).parent.parent / "downloads"
CHROME = DOWNLOADS / "chrome-linux64" / "chrome"
CHROMEDRIVER = DOWNLOADS / "chromedriver-linux64" / "chromedriver"


@pytest.fixture
def driver():
    if not CHROME.exists() or not CHROMEDRIVER.exists():
        pytest.fail("Chrome not found. Run `make chrome` first.")

    options = webdriver.ChromeOptions()
    options.binary_location = str(CHROME)
    options.add_argument("--headless=new")

    driver = webdriver.Chrome(service=Service(str(CHROMEDRIVER)), options=options)
    yield driver
    driver.quit()
