from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

DOWNLOADS = Path(__file__).parent.parent / "downloads"
CHROME = DOWNLOADS / "chrome-linux64" / "chrome"
CHROMEDRIVER = DOWNLOADS / "chromedriver-linux64" / "chromedriver"


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
