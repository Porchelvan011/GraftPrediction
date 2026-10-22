from appium.webdriver.common.appiumby import AppiumBy
from pages.base_page import BasePage

class CalculatorPage(BasePage):
    """Page Object for Graft Sizing Calculator Screen."""

    NAME_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Name') or contains(@text, 'Name')]")
    AGE_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Age') or contains(@text, 'Age')]")
    HEIGHT_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Height') or contains(@text, 'Height')]")
    WEIGHT_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Weight') or contains(@text, 'Weight')]")
    LEG_LENGTH_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Leg') or contains(@text, 'Leg')]")
    THIGH_LENGTH_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Thigh Length') or contains(@text, 'Thigh Length')]")
    THIGH_CIRC_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Circumference') or contains(@text, 'Circumference')]")
    POSTERIOR_ST_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Posterior ST') or contains(@text, 'Posterior ST')]")
    POSTERIOR_GRACILIS_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Posterior Gracilis') or contains(@text, 'Posterior Gracilis')]")
    LATERAL_ST_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Lateral ST') or contains(@text, 'Lateral ST')]")
    LATERAL_GRACILIS_INPUT = (AppiumBy.XPATH, "//android.widget.EditText[contains(@hint, 'Lateral Gracilis') or contains(@text, 'Lateral Gracilis')]")
    CALCULATE_BUTTON = (AppiumBy.XPATH, "//android.widget.Button[contains(@text, 'Calculate') or contains(@content-desc, 'Calculate')]")
    RESULT_CONTAINER = (AppiumBy.XPATH, "//*[contains(@text, 'Predicted ST') or contains(@text, 'Graft Diameter')]")
    SAVE_REPORT_BUTTON = (AppiumBy.XPATH, "//android.widget.Button[contains(@text, 'Save') or contains(@content-desc, 'Save')]")

    def fill_calculator_form(self, patient_data):
        if "name" in patient_data:
            self.send_keys(*self.NAME_INPUT, str(patient_data["name"]))
        if "age" in patient_data:
            self.send_keys(*self.AGE_INPUT, str(patient_data["age"]))
        if "height" in patient_data:
            self.send_keys(*self.HEIGHT_INPUT, str(patient_data["height"]))
        if "weight" in patient_data:
            self.send_keys(*self.WEIGHT_INPUT, str(patient_data["weight"]))
        if "leg_length" in patient_data:
            self.send_keys(*self.LEG_LENGTH_INPUT, str(patient_data["leg_length"]))
        if "thigh_length" in patient_data:
            self.send_keys(*self.THIGH_LENGTH_INPUT, str(patient_data["thigh_length"]))
        if "thigh_circ" in patient_data:
            self.send_keys(*self.THIGH_CIRC_INPUT, str(patient_data["thigh_circ"]))
        if "posterior_st" in patient_data:
            self.send_keys(*self.POSTERIOR_ST_INPUT, str(patient_data["posterior_st"]))
        if "posterior_gracilis" in patient_data:
            self.send_keys(*self.POSTERIOR_GRACILIS_INPUT, str(patient_data["posterior_gracilis"]))
        if "lateral_st" in patient_data:
            self.send_keys(*self.LATERAL_ST_INPUT, str(patient_data["lateral_st"]))
        if "lateral_gracilis" in patient_data:
            self.send_keys(*self.LATERAL_GRACILIS_INPUT, str(patient_data["lateral_gracilis"]))

    def click_calculate(self):
        self.click(*self.CALCULATE_BUTTON)

    def is_result_displayed(self):
        return self.is_visible(*self.RESULT_CONTAINER)
