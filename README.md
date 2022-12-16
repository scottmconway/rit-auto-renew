# RIT Auto Renew
This is a super-simple script for auto-renewing alumni accounts for the Rochester Institute of Technology (RIT).

As of now, it uses selenium with [undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver) and _hardcoded calls to sleep_. But hey, it works, and it should log appropriately if it doesn't work for whatever reason.

**Disclaimer - I am not responsible for any consequences of the use of this script, including but not limited to account suspension.**

## Requirements
* python3
* selenium
* undetected-chromedriver
* gotify-handler (optional - if you wish to log to gotify)

## Configuration
There's not much to say here - a valid config file includes your username, password, and some settings for the logger. See `config.json.example` for an example.

## Arguments
|Short Name|Long Name|Type|Description|
|-|-|-|-|
||`--config`|`str`|Path to config file - defaults to `./config.json`|

## Usage
Simply run `python3 rit_auto_renew.py` with a valid config (and perhap a defined `--config` path).
