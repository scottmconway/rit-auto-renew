#!/usr/bin/env python3

import argparse
import json
import logging
import re
from time import sleep

import undetected_chromedriver
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

SHIB_LOGIN_URL = (
    "https://start.rit.edu/Shibboleth.sso/Login?target=https://start.rit.edu/Alumni"
)
SHIB_LOGIN_ERR_URL = 'https://shibboleth.main.ad.rit.edu/idp/profile/SAML2/Redirect/SSO'
ACCOUNT_RENEWED_REGEX = re.compile(
    r".*<p>Your alumni account has been renewed until ([0-9]{4}\-[0-9]{2}\-[0-9]{2})\.</p>.*"
)


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
    logging.basicConfig()
    logging_conf = config.get("logging", dict())
    logger.setLevel(logging_conf.get("log_level", logging.INFO))
    if "gotify" in logging_conf:
        from gotify_handler import GotifyHandler

        logger.addHandler(GotifyHandler(**logging_conf["gotify"]))

    try:
        chrome_options = webdriver.ChromeOptions()
        # chrome_options.headless = True
        driver = undetected_chromedriver.Chrome(options=chrome_options)

        driver.get(SHIB_LOGIN_URL)
        sleep(10)
        driver.find_element("id", "ritUsername").send_keys(config["username"])
        driver.find_element("id", "ritPassword").send_keys(
            config["password"] + Keys.RETURN
        )

        # wait for SAML flow to the renewal page
        sleep(10)

        # check if we're still at the login page
        if driver.current_url.split('?')[0] == SHIB_LOGIN_ERR_URL:
            logger.error('Error logging into Shibboleth - exiting')
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
