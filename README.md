# telegram-bot-deploy

[![build](https://travis-ci.org/ciotto/telegram-bot-deploy.svg?branch=master)](https://travis-ci.org/ciotto/telegram-bot-deploy)
[![coverage](https://img.shields.io/codecov/c/gh/ciotto/telegram-bot-deploy)](https://codecov.io/gh/ciotto/telegram-bot-deploy)
[![Py Versions](https://img.shields.io/pypi/pyversions/telegram-bot-deploy)](https://pypi.python.org/pypi/telegram-bot-deploy/)
[![license](https://img.shields.io/github/license/ciotto/telegram-bot-deploy)](https://pypi.python.org/pypi/telegram-bot-deploy/)
[![status](https://img.shields.io/pypi/status/telegram-bot-deploy)](https://pypi.python.org/pypi/telegram-bot-deploy/)
[![PEP8](https://img.shields.io/badge/code%20style-pep8-orange)](https://www.python.org/dev/peps/pep-0008/)

**telegram-bot-deploy** is *simple* and *easy-to-use* script that perform continuous deployment for the **Telegram bots**.

## Installation

You can install **telegram-bot-deploy** from *PyPi*:

`pip install telegram-bot-deploy`

or from GitHub:

`pip install https://github.com/ciotto/telegram-bot-deploy/archive/master.zip`

## How to use

You can use **telegram-bot-deploy** with the command `tbd -u git@github.com:your/repo.git`.

There are many configurable parameters. You can see all configuration using command `tbd -h`.

Is also possible to use environments variables or a `.env` file in order to set basic configuration.

The available variables are:

  - `REPO_URL`: The URL of the repo to be used
  - `REPO_PATH`: The local path of the repo
  - `BRANCH`: The branch used for deploy

  - `SSH_KEY`: The SSH key to be used to authenticate to the repo

  - `CHAT_ID`: The chat ID used for bot communication
  - `BOT_TOKEN`: The bot token used for bot communication

  - `MSG_CREATE_VIRTUALENV_FAIL`: Message that will be send when create virtualenv fail
  - `MSG_INSTALL_REQUIREMENTS_FAIL`: Message that will be send when install requirements fail
  - `MSG_RUN_TESTS_FAIL`: Message that will be send when run tests fail
  - `MSG_COVERAGE_FAIL`: Message that will be send when get coverage fail
  - `MSG_COVERAGE_LOW`: Message that will be send when coverage is too low
  - `MSG_RESTART_FAIL`: Message that will be send when bot restart fail
  - `MSG_NEW_VERSION`: Message that will be send when new version was deployed

  - `PID_FILE_PATH`: The path to the PID file

  - `PYTHON_EXECUTABLE`: The Python executable
  - `VIRTUALENV_PATH`: The path to the Python virtualenv
  - `CREATE_VIRTUALENV`: The command used in order to create the Python virtualenv

  - `REQUIREMENTS_PATH`: The path to the requirements file
  - `INSTALL_REQUIREMENTS`: The command used in order to install the requirements

  - `RUN_TESTS`: The command used in order to run the tests
  - `MIN_COVERAGE`: The minimal coverage required in order to deploy
  - `GET_COVERAGE_PERCENTAGE`: The command used in order to get the coverage percentage value

  - `RUN_BOT`: The command used in order to run the bot

  - `LOGGING_FORMAT`: The format for Python logging
  - `LOGGING_LEVEL`: The level for Python logging
  - `LOGGING_FILENAME`: The filename for Python logging 

## How to contribute

This is not a big library but if you want to contribute is very easy!

 1. clone the repository `git clone https://github.com/ciotto/telegram-bot-deploy.git`
 1. install all requirements `make init`
 1. do your fixes or add new awesome features (with tests)
 1. run the tests `make test`
 1. commit in new branch and make a pull request

You chan use **telegram-bot-deploy** development version with the command `python -m bot_ci`.

---


## License

Released under [MIT License](https://github.com/ciotto/telegram-bot-deploy/blob/master/LICENSE).
