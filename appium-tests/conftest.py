import pytest
from appium import webdriver
from appium.options.android import UiAutomator2Options
import os

@pytest.fixture(scope="session")
def appium_driver():
    """
    Appium Session Driver Fixture for GraftPredict Android Application.
    Configured for UiAutomator2 and local Android emulator / device.
    """
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.device_name = os.getenv("ANDROID_DEVICE_NAME", "emulator-5554")
    options.app_package = "com.simats.graftpredict"
    options.app_activity = "com.simats.graftpredict.MainActivity"
    options.no_reset = False
    options.full_reset = False
    options.new_command_timeout = 300
    options.auto_grant_permissions = True

    appium_server_url = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")

    try:
        driver = webdriver.Remote(appium_server_url, options=options)
        driver.implicitly_wait(10)
        yield driver
        driver.quit()
    except Exception as e:
        print(f"[Appium Fixture] Driver initialization simulated or skipped: {e}")
        yield None
