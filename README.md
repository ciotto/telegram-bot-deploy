# telegram-bot-deploy

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

  - `REPO_URL`: The format for Python logging
  - `REPO_PATH`: The level for Python logging
  - `BRANCH`: The filename for Python logging

  - `SSH_KEY`: The URL of the repo to be used

  - `CHAT_ID`: The local path of the repo
  - `BOT_TOKEN`: The branch used for deploy
  - `MSG_TEXT`: Restart also same versions

  - `PID_FILE_PATH`: The SSH key to be used to authenticate to the repo

  - `PYTHON_EXECUTABLE`: The chat ID used for bot communication
  - `VIRTUALENV_PATH`: The bot token used for bot communication
  - `CREATE_VIRTUALENV`: The message that will be sent after update

  - `REQUIREMENTS_PATH`: The path to the PID file
  - `INSTALL_REQUIREMENTS`: The Python executable

  - `RUN_TESTS`: The path to the Python virtualenv

  - `RUN_BOT`: The command used in order to create the Python virtualenv

  - `LOGGING_FORMAT`: The path to the requirements file
  - `LOGGING_LEVEL`: The command used in order to install the requirements
  - `LOGGING_FILENAME`: The command used in order to run the tests 

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
