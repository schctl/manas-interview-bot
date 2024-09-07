import log
from config import Config

import os
import time
import sys

from contextlib import contextmanager

from alright import WhatsApp
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromiumService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from selenium.webdriver.chrome.options import Options as ChromeOptions

import phonenumbers
from phonenumbers import PhoneNumber


TEST_GUARD = True


class WhatsappInstance:
    def __init__(self, config: Config):
        self.config = config
        self.whatsapp = WhatsApp(self.setup_browser())
        pass

    @property
    def chrome_options(self) -> ChromeOptions:
        data_path = os.path.abspath("./.data")

        chrome_options = ChromeOptions()
        if sys.platform == "win32":
            chrome_options.add_argument("--profile-directory=Default")
            chrome_options.add_argument(f"--user-data-dir={data_path}\\{self.config.safety.name}")
        else:
            chrome_options.add_argument("start-maximized")
            chrome_options.add_argument(f"--user-data-dir={data_path}/{self.config.safety.name}")
        return chrome_options

    def setup_browser(self) -> webdriver.Chrome:
        chromium = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
        driver = webdriver.Chrome(service=ChromiumService(chromium), options=self.chrome_options)

        return driver

    @contextmanager
    def direct(self, num: PhoneNumber):
        try:
            guard = _WGuard(self, num)
            yield guard
        finally:
            pass

class _WGuard:
    def __init__(self, whatsapp: WhatsappInstance, num: PhoneNumber):
        self.instance = whatsapp
        self.num = num

    def send(self, message: str):
        num_f = phonenumbers.format_number(self.num, phonenumbers.PhoneNumberFormat.E164).lstrip('+')

        if TEST_GUARD:
            with open("./.safety", "r") as f:
                num_f = f.read().strip()

        log.info(num_f)

        self.instance.whatsapp.send_direct_message(num_f, message, saved=False)
        self.instance.whatsapp.wait_until_message_successfully_sent()


w = WhatsappInstance(Config())

with w.direct(phonenumbers.parse("+966 50 521 1235", "IN")) as x:
    x.send("Hello, world!")
