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


def getenv(key, default=None, parser=None):
    value = os.getenv(key, default)
    if value and parser:
        return parser(value)
    return value


REPO_URL = getenv('REPO_URL')
REPO_PATH = getenv('REPO_PATH', 'repo')
BRANCH = getenv('BRANCH', 'master')

SSH_KEY = getenv('SSH_KEY', 'id_deployment_key')
CHAT_ID = getenv('CHAT_ID', parser=int)
BOT_TOKEN = getenv('BOT_TOKEN')
MSG_TEXT = getenv('MSG_TEXT', "I'm at new version %(version)s!")

PID_FILE_PATH = getenv('PID_FILE_PATH')

VIRTUALENV_PATH = getenv('VIRTUALENV_PATH', '.virtualenv')
CREATE_VIRTUALENV = getenv('CREATE_VIRTUALENV')

REQUIREMENTS_PATH = getenv('REQUIREMENTS_PATH', 'requirements.txt')
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
            branch=BRANCH,

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
        self.repo_path = repo_path
        self.branch = branch

        self.msg_text = msg_text

        # SSH config
        self.ssh_key = os.path.abspath(ssh_key)
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
        self.virtualenv_path = virtualenv_path
        self.create_virtualenv = create_virtualenv.split(' ') if create_virtualenv else [
            'virtualenv', self.virtualenv_path, '--system-site-packages', '-p', self.python_executable
        ]

        # Requirements
        self.requirements_path = requirements_path
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

        # True when local branch does not exist
        self.is_new_repo = False

        self.tags_map = {}

        # The pid of the daemon process
        self.pid = None

        # Versions name
        self.old_version = None
        self.version = None

        # Last commit on remote
        self.remote_commit = None

        # The last tag on branch
        self.last_tag = None

        # Author of this version
        self.author = None

        self.check()

    def error(self, msg):
        logging.error(msg)
        exit(1)

    def check(self):
        """Check config"""
        # TODO Do more check
        if not self.repo_url:
            self.error('Missing repo_url')

    def get_last_tag(self, commit):
        """Find last tag by commit"""
        if self.tags_map:
            while True:
                if commit in self.tags_map:
                    return self.tags_map[commit]
                elif not commit.parents:
                    break
                # TODO check with merge
                commit = commit.parents[0]
        return None

    def call_create_virtualenv(self):
        """Create virtualenv if not exist"""
        if self.virtualenv_path and not os.path.exists(self.virtualenv_path):
            logging.info('Create virtualenv: %s' % ' '.join(self.create_virtualenv))
            process = subprocess.Popen(self.create_virtualenv, cwd=self.repo_path)
            process.wait()
        else:
            logging.info('Virtualenv %s already exist' % self.virtualenv_path)

    def call_install_requirements(self):
        """Install requirements"""
        logging.info('Install requirements: %s' % ' '.join(self.install_requirements))
        process = subprocess.Popen(self.install_requirements, cwd=self.repo_path)
        process.wait()

    def call_run_tests(self):
        """Run tests"""
        if self.run_tests and not self.skip_tests:
            logging.info('Run tests %s' % ' '.join(self.run_tests))
            process = subprocess.Popen(self.run_tests, cwd=self.repo_path)
            process.wait()

    def stop_bot(self):
        """Stop running bot"""
        # Check pid file
        if os.path.exists(self.pid_file_path):
            logging.info('Stop started bot')
            try:
                with open(self.pid_file_path, 'r') as f:
                    pid = int(f.read())
                os.kill(pid, signal.SIGTERM)
            except OSError:
                logging.info('Process already stopped')

    def start_bot(self):
        """Start the bot"""
        # Run bot
        logging.info('Run bot %s: %s' % (self.version, ' '.join(self.run_bot)))
        process = subprocess.Popen(self.run_bot, cwd=self.repo_path)
        self.pid = process.pid

        # Save pid
        logging.info('Save pid %s' % self.pid)
        with open(self.pid_file_path, 'w') as f:
            f.write(str(self.pid))

    def restart_bot(self):
        """Stop and restart the bot"""
        self.stop_bot()
        self.start_bot()

    def send_message(self, msg):
        if self.bot and self.chat_id:
            logging.info('Send message to %s: %s' % (self.chat_id, msg))
            self.bot.send_message(
                chat_id=self.chat_id,
                text=msg,
            )
        else:
            logging.info('Bot token or chat_id not configured')

    def send_new_version_message(self):
        self.send_message(self.msg_text % {
                'old_version': self.old_version,
                'version': self.version,
                'author': self.author,
        })

    def run(self):
        self.is_new_repo = not os.path.exists(self.repo_path)

        if self.is_new_repo:
            logging.info('Clone repo %s to %s' % (self.repo_url, self.repo_path))
            Repo.clone_from(self.repo_url, self.repo_path, env={'GIT_SSH_COMMAND': self.ssh_cmd})

        # Init repo
        logging.info('Init repo %s' % self.repo_path)
        repo = Repo.init(self.repo_path)

        # Set old version
        self.old_version = repo.git.describe('--always')

        # Generate tags map
        self.tags_map = dict(map(lambda x: (x.commit, x), repo.tags))

        # Fetch origin
        logging.info('Fetch remote %s' % self.repo_url)
        with repo.git.custom_environment(GIT_SSH_COMMAND=self.ssh_cmd):
            repo.remotes.origin.fetch(['--tags', '-f'])

            for ref in repo.remotes.origin.refs:
                if ref.name == 'origin/%s' % self.branch:
                    self.remote_commit = ref

            if not self.remote_commit:
                self.error('Missing origin/%s' % self.branch)

        # Find last tag on branch
        self.last_tag = self.get_last_tag(self.remote_commit.commit)

        # Go to last tag
        if self.last_tag:
            # Set version name
            self.version = self.last_tag.name

            # Set author name
            self.author = self.last_tag.tag.object.author.name

            if self.last_tag.tag.object != repo.head.commit:
                # Go to last tag
                repo.head.reset(self.last_tag, index=True, working_tree=True)

                # Release
                self.call_create_virtualenv()

                self.call_install_requirements()

                self.call_run_tests()

                self.restart_bot()

                self.send_new_version_message()
            else:
                logging.info('Repo up to date on %s' % self.version)
        else:
            logging.info('No tags on branch %s' % self.branch)


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
    parser.add_argument('-b', '--branch', nargs='?', type=str, default=None,
                        help='The branch used for deploy')

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

