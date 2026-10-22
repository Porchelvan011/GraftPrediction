import pytest
from pages.login_page import LoginPage
from pages.calculator_page import CalculatorPage
from pages.reports_page import ReportsPage

@pytest.mark.usefixtures("appium_driver")
class TestGraftPredictE2E:
    """End-to-End Functional Test Suite for GraftPredict App."""

    def test_001_login_validation_empty_fields(self, appium_driver):
        """TC_AUTH_001: Validate error when logging in with empty credentials."""
        if not appium_driver:
            pytest.skip("Appium driver not connected in headless CI")
        login_page = LoginPage(appium_driver)
        login_page.login("", "")
        assert login_page.is_error_displayed()

    def test_002_login_invalid_email_format(self, appium_driver):
        """TC_AUTH_002: Validate error on malformed email input."""
        if not appium_driver:
            pytest.skip("Appium driver not connected in headless CI")
        login_page = LoginPage(appium_driver)
        login_page.login("invaliduser@@domain", "Pass1234!")
        assert login_page.is_error_displayed()

    def test_003_navigate_to_forgot_password(self, appium_driver):
        """TC_AUTH_003: Verify navigation to forgot password screen."""
        if not appium_driver:
            pytest.skip("Appium driver not connected in headless CI")
        login_page = LoginPage(appium_driver)
        login_page.click_forgot_password()

    def test_004_graft_size_calculation_happy_path(self, appium_driver):
        """TC_CALC_001: Calculate graft size with standard valid inputs."""
        if not appium_driver:
            pytest.skip("Appium driver not connected in headless CI")
        calc_page = CalculatorPage(appium_driver)
        calc_page.fill_calculator_form({
            "name": "John Doe",
            "age": 28,
            "height": 175.0,
            "weight": 70.0,
            "leg_length": 85.0,
            "thigh_length": 45.0,
            "thigh_circ": 52.0,
            "posterior_st": 4.5,
            "posterior_gracilis": 3.2,
            "lateral_st": 4.8,
            "lateral_gracilis": 3.4
        })
        calc_page.click_calculate()
        assert calc_page.is_result_displayed()
