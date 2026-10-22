from appium.webdriver.common.appiumby import AppiumBy
from pages.base_page import BasePage

class LoginPage(BasePage):
    """Page Object for GraftPredict Login Screen."""

    EMAIL_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@text, 'Email') or contains(@hint, 'Email')]")
    PASSWORD_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@text, 'Password') or contains(@hint, 'Password')]")
    SIGN_IN_BUTTON = (AppiumBy.XPATH, "//android.widget.Button[contains(@text, 'Sign In') or contains(@content-desc, 'Sign In')]")
    FORGOT_PASSWORD_LINK = (AppiumBy.XPATH, "//*[@text='Forgot Password?' or contains(@content-desc, 'Forgot Password')]")
    SIGN_UP_LINK = (AppiumBy.XPATH, "//*[contains(@text, 'Sign Up') or contains(@content-desc, 'Sign Up')]")
    ERROR_SNACKBAR = (AppiumBy.XPATH, "//*[contains(@resource-id, 'snackbar') or contains(@text, 'Invalid') or contains(@text, 'Error')]")
    GOOGLE_SIGN_IN_BUTTON = (AppiumBy.XPATH, "//*[contains(@text, 'Google') or contains(@content-desc, 'Google')]")

    def login(self, email, password):
        self.send_keys(*self.EMAIL_INPUT, email)
        self.send_keys(*self.PASSWORD_INPUT, password)
        self.click(*self.SIGN_IN_BUTTON)

    def click_forgot_password(self):
        self.click(*self.FORGOT_PASSWORD_LINK)

    def click_sign_up(self):
        self.click(*self.SIGN_UP_LINK)

    def is_error_displayed(self):
        return self.is_visible(*self.ERROR_SNACKBAR)
