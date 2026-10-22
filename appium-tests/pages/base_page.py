from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

class BasePage:
    """Base Page Object containing reusable UI interaction methods for Appium."""
    
    def __init__(self, driver):
        self.driver = driver
        self.timeout = 15

    def find_element(self, by, locator, timeout=None):
        wait = WebDriverWait(self.driver, timeout or self.timeout)
        return wait.until(EC.presence_of_element_located((by, locator)))

    def click(self, by, locator):
        element = self.find_element(by, locator)
        element.click()

    def send_keys(self, by, locator, text):
        element = self.find_element(by, locator)
        element.clear()
        element.send_keys(text)

    def get_text(self, by, locator):
        element = self.find_element(by, locator)
        return element.text

    def is_visible(self, by, locator, timeout=5):
        try:
            WebDriverWait(self.driver, timeout).until(EC.visibility_of_element_located((by, locator)))
            return True
        except TimeoutException:
            return False

    def scroll_into_view_by_text(self, text):
        ui_scroll = f'new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector().text("{text}"))'
        return self.driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, ui_scroll)
