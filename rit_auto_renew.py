#!/usr/bin/env python3

import argparse
import json
import logging
import logging.config
import platform
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from time import sleep
from urllib.request import urlopen

import undetected_chromedriver
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

CHROME_VERSION = "158.0.8127.36"
SHIB_LOGIN_URL = (
    "https://start.rit.edu/Shibboleth.sso/Login?target=https://start.rit.edu/Alumni"
)
SHIB_LOGIN_ERR_URL = "https://shibboleth.main.ad.rit.edu/idp/profile/SAML2/Redirect/SSO"
ACCOUNT_RENEWED_REGEX = re.compile(
    r".*<p>Your alumni account has been renewed until ([0-9]{4}\-[0-9]{2}\-[0-9]{2})\.</p>.*"
)


def chrome_platform():
    system = platform.system()
    machine = platform.machine().lower()
    platforms = {
        ("Linux", "x86_64"): "linux64",
        ("Linux", "amd64"): "linux64",
        ("Darwin", "x86_64"): "mac-x64",
        ("Darwin", "arm64"): "mac-arm64",
        ("Windows", "amd64"): "win64",
        ("Windows", "x86_64"): "win64",
        ("Windows", "x86"): "win32",
        ("Windows", "i386"): "win32",
        ("Windows", "i686"): "win32",
    }
    try:
        return platforms[(system, machine)]
    except KeyError:
        raise RuntimeError(
            f"Unsupported Chrome/undetected-chromedriver platform: {system} {machine}"
        ) from None


def get_chrome_binary(logger):
    target = chrome_platform()
    cache_dir = Path.cwd() / f"chrome_{CHROME_VERSION}"
    if target.startswith("mac-"):
        binary_path = Path(
            "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
        )
    else:
        binary_path = Path("chrome.exe" if target.startswith("win") else "chrome")

    binary = cache_dir / binary_path
    if cache_dir.exists():
        if not binary.is_file():
            raise FileNotFoundError(f"Local Chrome installation is incomplete: {binary}")
        return binary

    url = (
        "https://storage.googleapis.com/chrome-for-testing-public/"
        f"{CHROME_VERSION}/{target}/chrome-{target}.zip"
    )
    logger.info(f"Downloading Chrome {CHROME_VERSION} for {target}")
    with tempfile.TemporaryDirectory(prefix=".chrome-download-", dir=Path.cwd()) as tmp:
        staging = Path(tmp)
        archive_path = staging / "chrome.zip"
        with urlopen(url, timeout=60) as response, archive_path.open("wb") as output:
            shutil.copyfileobj(response, output)

        if target.startswith("mac-"):
            # ditto preserves the application bundle's symlinks and permissions.
            subprocess.run(
                ["/usr/bin/ditto", "-x", "-k", str(archive_path), str(staging)],
                check=True,
            )
        else:
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(staging)
                if target == "linux64":
                    for entry in archive.infolist():
                        if not entry.is_dir():
                            mode = (entry.external_attr >> 16) & 0o777
                            if mode:
                                (staging / entry.filename).chmod(mode)

        extracted = staging / f"chrome-{target}"
        staged_binary = extracted / binary_path
        if not staged_binary.is_file():
            raise FileNotFoundError(f"Chrome archive is missing {binary_path}")
        if not target.startswith("win"):
            staged_binary.chmod(staged_binary.stat().st_mode | 0o111)
        extracted.rename(cache_dir)
    return binary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to config file - defaults to ./config.json",
    )
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)

    logger = logging.getLogger("rit_auto_renew")
    logging_conf = config.get("logging", dict())
    logging.config.dictConfig(logging_conf)

    try:
        chrome_binary = get_chrome_binary(logger)
        chrome_options = webdriver.ChromeOptions()
        # chrome_options.headless = True
        driver = undetected_chromedriver.Chrome(
            options=chrome_options,
            browser_executable_path=str(chrome_binary),
            version_main=int(CHROME_VERSION.split(".")[0]),
            headless=True,
        )

        driver.get(SHIB_LOGIN_URL)
        sleep(10)
        driver.find_element("id", "ritUsername").send_keys(config["username"])
        driver.find_element("id", "ritPassword").send_keys(
            config["password"] + Keys.RETURN
        )

        # wait for SAML flow to the renewal page
        sleep(10)

        # check if we're still at the login page
        if driver.current_url.split("?")[0] == SHIB_LOGIN_ERR_URL:
            logger.error("Error logging into Shibboleth - exiting")
            return

        # click the "renew" button
        driver.find_element("class name", "fa-sync").click()

        # wait for the page to update with our renewal status
        sleep(10)

        regex_res = ACCOUNT_RENEWED_REGEX.findall(driver.page_source)
        if regex_res:
            logger.info(f"Account renewed until {regex_res[0]}")
        else:
            logger.error("Did not find renewal notice!")

    except BaseException as be:
        logger.error(f"{type(be).__name__} - {be}")


if __name__ == "__main__":
    main()
