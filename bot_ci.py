import argparse
import logging
import os
import signal
import subprocess

import telegram
from dotenv import load_dotenv, find_dotenv
from git import Repo

# Load .env
load_dotenv(find_dotenv())


def getenv(key, parser=None):
    value = os.getenv(key, None)
    if value and parser:
        return parser(value)
    return value


REPO_URL = getenv('REPO_URL')
REPO_PATH = getenv('REPO_PATH', 'repo')

SSH_KEY = getenv('SSH_KEY')
CHAT_ID = getenv('CHAT_ID', int)
BOT_TOKEN = getenv('BOT_TOKEN')
MSG_TEXT = getenv('MSG_TEXT')

PID_FILE_PATH = getenv('PID_FILE_PATH')

VIRTUALENV_PATH = getenv('VIRTUALENV_PATH')
CREATE_VIRTUALENV = getenv('CREATE_VIRTUALENV')

REQUIREMENTS_PATH = getenv('REQUIREMENTS_PATH')
INSTALL_REQUIREMENTS = getenv('INSTALL_REQUIREMENTS')

RUN_TESTS = getenv('RUN_TESTS')

RUN_BOT = getenv('RUN_BOT')

LOGGING_FORMAT = getenv('LOGGING_FORMAT')
LOGGING_LEVEL = getenv('LOGGING_LEVEL')
LOGGING_FILENAME = getenv('LOGGING_FILENAME')


class BotCi:
    def __init__(
            self,
            repo_url=REPO_URL,
            repo_path=REPO_PATH,

            force=False,

            ssh_key=SSH_KEY,

            chat_id=CHAT_ID,
            bot_token=BOT_TOKEN,
            msg_text=MSG_TEXT,

            pid_file_path=PID_FILE_PATH,

            virtualenv_path=VIRTUALENV_PATH,
            create_virtualenv=CREATE_VIRTUALENV,

            requirements_path=REQUIREMENTS_PATH,
            install_requirements=INSTALL_REQUIREMENTS,

            run_tests=RUN_TESTS,
            skip_tests=False,

            run_bot=RUN_BOT,
    ):
        # Set defaults
        self.repo_url = repo_url
        self.repo_path = repo_path or 'repo'

        self.msg_text = msg_text or "I'm at new version %(version)s!"

        # SSH config
        self.ssh_key = os.path.abspath(ssh_key or 'id_deployment_key')
        self.ssh_cmd = 'ssh -i %s' % self.ssh_key

        # Bot config
        self.chat_id = chat_id
        self.bot_token = bot_token
        self.msg_text = msg_text
        self.bot = None
        if self.bot_token:
            self.bot = telegram.Bot(self.bot_token)

        # pid file
        self.pid_file_path = pid_file_path or os.path.join(self.repo_path, '.pid')

        self.force = force

        # Virtualenv
        self.python_executable = 'python3'
        self.virtualenv_path = virtualenv_path or '.virtualenv'
        self.create_virtualenv = create_virtualenv.split(' ') if create_virtualenv else [
            'virtualenv', self.virtualenv_path, '--system-site-packages', '-p', self.python_executable
        ]

        # Requirements
        self.requirements_path = requirements_path or 'requirements.txt'
        self.install_requirements = install_requirements.split(' ') if install_requirements else [
            os.path.join(self.virtualenv_path, 'bin', 'pip'), 'install', '-r', self.requirements_path
        ]

        # Tests
        self.run_tests = run_tests.split(' ') if run_tests else [
            os.path.join(self.virtualenv_path, 'bin', 'pytest')
        ]
        self.skip_tests = skip_tests

        # Run
        self.run_bot = run_bot.split(' ') if run_bot else [
            os.path.join(self.virtualenv_path, 'bin', 'python'), 'bot.py'
        ]

        self.new_repo = False
        self.pid = None
        self.version = None

    def check(self):
        # TODO Do more check
        if not self.repo_url:
            logging.error('Missing repo_url')
            exit(1)

    def run(self):
        self.check()

        self.new_repo = not os.path.exists(self.repo_path)

        if self.new_repo:
            logging.info('Clone repo %s to %s' % (self.repo_url, self.repo_path))
            Repo.clone_from(self.repo_url, self.repo_path, env={'GIT_SSH_COMMAND': self.ssh_cmd})

        # Init repo
        logging.info('Init repo %s' % self.repo_path)
        repo = Repo.init(self.repo_path)

        # Fetch origin
        logging.info('Fetch remote %s' % self.repo_url)
        with repo.git.custom_environment(GIT_SSH_COMMAND=self.ssh_cmd):
            repo.remotes.origin.fetch(['--tags', '-f'])

        old_version = repo.git.describe('--always')

        # Go to last tag
        if repo.tags:
            repo.head.reset(repo.tags[-1], index=True, working_tree=True)

            # Get version
            self.version = repo.tags[-1].name

            if self.new_repo or old_version != self.version or self.force:
                # Create virtualenv
                if self.virtualenv_path and not os.path.exists(self.virtualenv_path):
                    logging.info('Create virtualenv: %s' % ' '.join(self.create_virtualenv))
                    process = subprocess.Popen(self.create_virtualenv, cwd=self.repo_path)
                    process.wait()

                # Install requirements
                logging.info('Install requirements: %s' % ' '.join(self.install_requirements))
                process = subprocess.Popen(self.install_requirements, cwd=self.repo_path)
                process.wait()

                # Run tests
                if self.run_tests and not self.skip_tests:
                    logging.info('Run tests %s' % ' '.join(self.run_tests))
                    process = subprocess.Popen(self.run_tests, cwd=self.repo_path)
                    process.wait()

                # Check pid file
                if os.path.exists(self.pid_file_path):
                    logging.info('Stop started bot')
                    try:
                        with open(self.pid_file_path, 'r') as f:
                            pid = int(f.read())
                        os.kill(pid, signal.SIGTERM)
                    except OSError:
                        logging.info('Process already stopped')

                # Run bot
                logging.info('Run bot %s: %s' % (self.version, ' '.join(self.run_bot)))
                process = subprocess.Popen(self.run_bot)
                self.pid = process.pid

                if self.bot:
                    msg_text = self.msg_text % {
                        'version': self.version,
                    }
                    logging.info('Send message to %s: %s' % (self.chat_id, msg_text))
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=msg_text,
                    )

                # Save pid
                logging.info('Save pid %s' % self.pid)
                with open(self.pid_file_path, 'w') as f:
                    f.write(str(self.pid))
            else:
                logging.info('Repo up to date on %s' % self.version)
        else:
            logging.info('No tags')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test and deploy a telegram bot.')

    parser.add_argument('-F', '--logging_format', nargs='?', type=str, default=None,
                        help='The format for Python logging')
    parser.add_argument('-l', '--logging_level', nargs='?', type=str, default=None,
                        help='The level for Python logging')
    parser.add_argument('-f', '--logging_filename', nargs='?', type=str, default=None,
                        help='The filename for Python logging')

    parser.add_argument('-u', '--repo_url', nargs='?', type=str, default=None,
                        help='The URL of the repo to be used')
    parser.add_argument('-p', '--repo_path', nargs='?', type=str, default=None,
                        help='The local path of the repo')

    parser.add_argument('-O', '--force', action='store_true',
                        help='Restart also same versions')

    parser.add_argument('-k', '--ssh_key', nargs='?', type=str, default=None,
                        help='The SSH key to be used to authenticate to the repo')

    parser.add_argument('-c', '--chat_id', nargs='?', type=str, default=None,
                        help='The chat ID used for bot communication')
    parser.add_argument('-t', '--bot_token', nargs='?', type=str, default=None,
                        help='The bot token used for bot communication')
    parser.add_argument('-m', '--msg_text', nargs='?', type=str, default=None,
                        help='The message that will be sent after update')

    parser.add_argument('-P', '--pid_file_path', nargs='?', type=str, default=None,
                        help='The path to the PID file')

    parser.add_argument('-v', '--virtualenv_path', nargs='?', type=str, default=None,
                        help='The path to the Python virtualenv')
    parser.add_argument('-C', '--create_virtualenv', nargs='?', type=str, default=None,
                        help='The command used in order to create the Python virtualenv')

    parser.add_argument('-r', '--requirements_path', nargs='?', type=str, default=None,
                        help='The path to the requirements file')
    parser.add_argument('-I', '--install_requirements', nargs='?', type=str, default=None,
                        help='The command used in order to install the requirements')

    parser.add_argument('-T', '--run_tests', nargs='?', type=str, default=None,
                        help='The command used in order to run the tests')
    parser.add_argument('-s', '--skip_tests', action='store_true',
                        help='Skip tests')

    parser.add_argument('-R', '--run_bot', nargs='?', type=str, default=None,
                        help='The command used in order to run the bot')

    args = {k: v for k, v in vars(parser.parse_args()).items() if v is not None}

    # Set logging
    logging_format = args.pop('logging_format', None) or LOGGING_FORMAT or '%(asctime)s - %(levelname)s - %(message)s'
    logging_level = args.pop('logging_level', None) or LOGGING_LEVEL or logging.INFO
    logging_filename = args.pop('logging_filename', None) or LOGGING_FILENAME

    logging.basicConfig(
        filename=logging_filename,
        format=logging_format,
        level=logging_level,
    )
    logger = logging.getLogger(__name__)

    # Start CI
    bot_cd = BotCi(**args)
    bot_cd.run()

