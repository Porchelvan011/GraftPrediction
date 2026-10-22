from appium.webdriver.common.appiumby import AppiumBy
from pages.base_page import BasePage

class ReportsPage(BasePage):
    """Page Object for Patient Reports Management & Sharing Screen."""

    SEARCH_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Search') or contains(@text, 'Search')]")
    REPORT_ITEM = (AppiumBy.XPATH, "//*[contains(@resource-id, 'report_item') or contains(@text, 'Report #')]")
    SHARE_BUTTON = (AppiumBy.XPATH, "//*[contains(@text, 'Share') or contains(@content-desc, 'Share')]")
    DELETE_BUTTON = (AppiumBy.XPATH, "//*[contains(@text, 'Delete') or contains(@content-desc, 'Delete')]")
    CONFIRM_DELETE_BTN = (AppiumBy.XPATH, "//android.widget.Button[contains(@text, 'Yes') or contains(@text, 'Confirm')]")
    DOCTOR_EMAIL_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Doctor Email') or contains(@text, 'Doctor Email')]")
    SEND_REPORT_BUTTON = (AppiumBy.XPATH, "//android.widget.Button[contains(@text, 'Send') or contains(@content-desc, 'Send')]")

    def search_report(self, query):
        self.send_keys(*self.SEARCH_INPUT, query)

    def select_first_report(self):
        self.click(*self.REPORT_ITEM)

    def share_report_to_doctor(self, doctor_email):
        self.click(*self.SHARE_BUTTON)
        self.send_keys(*self.DOCTOR_EMAIL_INPUT, doctor_email)
        self.click(*self.SEND_REPORT_BUTTON)

    def delete_first_report(self):
        self.click(*self.DELETE_BUTTON)
        self.click(*self.CONFIRM_DELETE_BTN)
