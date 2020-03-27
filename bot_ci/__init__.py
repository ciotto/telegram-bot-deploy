import argparse
import logging
import os
import signal
import subprocess

import telegram
from dotenv import load_dotenv, find_dotenv
from git import Repo

# Load .env
from bot_ci.utilities import getenv

logger = logging.getLogger(__name__)


# Read enviroment variable
def read_environments():
    # Load .env
    load_dotenv(find_dotenv())

    return dict(
        repo_url=getenv('REPO_URL'),
        repo_path=getenv('REPO_PATH'),
        branch=getenv('BRANCH', 'master'),

        ssh_key=getenv('SSH_KEY', 'id_deployment_key'),

        chat_id=getenv('CHAT_ID', parser=int),
        bot_token=getenv('BOT_TOKEN'),
        msg_text=getenv('MSG_TEXT', "I'm at new version %(version)s!"),

        pid_file_path=getenv('PID_FILE_PATH'),

        python_executable=getenv('PYTHON_EXECUTABLE'),
        virtualenv_path=getenv('VIRTUALENV_PATH', '.virtualenv'),
        create_virtualenv=getenv('CREATE_VIRTUALENV'),

        requirements_path=getenv('REQUIREMENTS_PATH'),
        install_requirements=getenv('INSTALL_REQUIREMENTS'),

        run_tests=getenv('RUN_TESTS'),

        run_bot=getenv('RUN_BOT'),

        logging_format=getenv('LOGGING_FORMAT', '%(asctime)s - %(levelname)s - %(message)s'),
        logging_level=getenv('LOGGING_LEVEL', logging.INFO, parser=int),
        logging_filename=getenv('LOGGING_FILENAME'),
    )


class BotCi:
    def __init__(
        self,
        repo_url=None,
        repo_path=None,
        branch=None,

        force=False,

        ssh_key=None,

        chat_id=None,
        bot_token=None,
        msg_text=None,

        pid_file_path=None,

        python_executable=None,
        virtualenv_path=None,
        create_virtualenv=None,

        requirements_path=None,
        install_requirements=None,

        run_tests=None,
        skip_tests=False,

        run_bot=None,
        **kwargs
    ):
        # Set defaults
        self.repo_url = repo_url
        self.repo_path = repo_path or 'repo'
        self.branch = branch

        # SSH config
        self.ssh_key = os.path.abspath(ssh_key) if ssh_key else None
        self.ssh_cmd = 'ssh -i %s' % self.ssh_key if self.ssh_key else None

        # Bot config
        self.chat_id = chat_id
        self.bot_token = bot_token
        self.bot = None
        if self.bot_token:
            self.bot = telegram.Bot(self.bot_token)
        self.msg_text = msg_text

        # pid file
        self.pid_file_path = pid_file_path or os.path.join(self.repo_path, '.pid')

        self.force = force

        # Virtualenv
        self.python_executable = python_executable or 'python3'
        self.virtualenv_path = virtualenv_path
        self.bin_path = os.path.join(self.virtualenv_path, 'bin') if self.virtualenv_path else None
        self.create_virtualenv = None
        if create_virtualenv:
            self.create_virtualenv = create_virtualenv.split(' ')
        elif self.virtualenv_path:
            self.create_virtualenv = [
                'virtualenv', self.virtualenv_path, '--no-site-packages', '-p', self.python_executable
            ]

        # Requirements
        self.requirements_path = requirements_path or 'requirements.txt'
        self.install_requirements = install_requirements.split(' ') if install_requirements else [
            os.path.join(self.bin_path or '', 'pip'), 'install', '-r', self.requirements_path
        ]

        # Tests
        self.run_tests = run_tests.split(' ') if run_tests else [
            os.path.join(self.bin_path or '', 'pytest')
        ]
        self.skip_tests = skip_tests

        # Run
        self.run_bot = run_bot.split(' ') if run_bot else [
            os.path.join(self.bin_path or '', 'python'), 'bot.py'
        ]

        # True when local branch does not exist
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

    def error(self, msg, code=os.EX_IOERR):
        logger.error(msg)
        os._exit(code)

    def check(self):
        """Check config"""
        # TODO Do more check
        if not self.repo_url:
            self.error('Missing repo_url', code=os.EX_DATAERR)

    @property
    def is_new_repo(self):
        return not os.path.exists(self.repo_path)

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
        if self.create_virtualenv:
            if self.virtualenv_path and not os.path.exists(self.virtualenv_path):
                logger.info('Create virtualenv: %s' % ' '.join(self.create_virtualenv))
                process = subprocess.Popen(self.create_virtualenv, cwd=self.repo_path)
                process.wait()
            else:
                logger.info('Virtualenv %s already exist' % self.virtualenv_path)

    def call_install_requirements(self):
        """Install requirements"""
        logger.info('Install requirements: %s' % ' '.join(self.install_requirements))
        process = subprocess.Popen(self.install_requirements, cwd=self.repo_path)
        process.wait()

    def call_run_tests(self):
        """Run tests"""
        if not self.skip_tests:
            logger.info('Run tests %s' % ' '.join(self.run_tests))
            process = subprocess.Popen(self.run_tests, cwd=self.repo_path)
            process.wait()

    def stop_bot(self):
        """Stop running bot"""
        # Check pid file
        if os.path.exists(self.pid_file_path):
            logger.info('Stop started bot')
            try:
                with open(self.pid_file_path, 'r') as f:
                    pid = int(f.read())
                os.kill(pid, signal.SIGTERM)
            except OSError:
                logger.info('Process already stopped')

    def start_bot(self):
        """Start the bot"""
        # Run bot
        logger.info('Run bot %s: %s' % (self.version, ' '.join(self.run_bot)))
        process = subprocess.Popen(self.run_bot, cwd=self.repo_path)
        self.pid = process.pid

        # Save pid
        logger.info('Save pid %s' % self.pid)
        with open(self.pid_file_path, 'w') as f:
            f.write(str(self.pid))

    def restart_bot(self):
        """Stop and restart the bot"""
        self.stop_bot()
        self.start_bot()

    def send_message(self, msg):
        """Send a message"""
        if self.bot and self.chat_id:
            logger.info('Send message to %s: %s' % (self.chat_id, msg))
            self.bot.send_message(
                chat_id=self.chat_id,
                text=msg,
            )
        else:
            logger.info('Bot token or chat_id not configured')

    def send_new_version_message(self):
        """Send a message when new version was deployed"""
        self.send_message(self.msg_text % {
                'old_version': self.old_version,
                'version': self.version,
                'author': self.author,
        })

    def clone_repo(self):
        """Clone repo if need"""
        if self.is_new_repo:
            logger.info('Clone repo %s to %s' % (self.repo_url, self.repo_path))
            Repo.clone_from(self.repo_url, self.repo_path, env={'GIT_SSH_COMMAND': self.ssh_cmd})

    def run(self):
        # Clone repo if need
        self.clone_repo()

        # Init repo
        logger.info('Init repo %s' % self.repo_path)
        repo = Repo.init(self.repo_path)

        # Set old version
        self.old_version = repo.git.describe('--always')

        # Fetch origin
        logger.info('Fetch remote %s' % self.repo_url)
        with repo.git.custom_environment(GIT_SSH_COMMAND=self.ssh_cmd):
            repo.remotes.origin.fetch(['--tags', '-f'])

            for ref in repo.remotes.origin.refs:
                if ref.name == 'origin/%s' % self.branch:
                    self.remote_commit = ref

            if not self.remote_commit:
                self.error('Missing origin/%s' % self.branch)

        # Find last tag on branch
        self.tags_map = dict(map(lambda x: (x.commit, x), repo.tags))
        self.last_tag = self.get_last_tag(self.remote_commit.commit)

        # Go to last tag
        if self.last_tag:
            # Set version name
            self.version = self.last_tag.name

            # Set author name
            self.author = self.last_tag.tag.object.author.name

            if self.last_tag.tag.object != repo.head.commit or self.force:
                # Go to last tag
                repo.head.reset(self.last_tag, index=True, working_tree=True)

                # Release
                self.call_create_virtualenv()

                self.call_install_requirements()

                self.call_run_tests()

                self.restart_bot()

                self.send_new_version_message()
            else:
                logger.info('Repo up to date on %s' % self.version)
        else:
            logger.info('No tags on branch %s' % self.branch)


def main():
    parser = argparse.ArgumentParser(description='Test and deploy a telegram bot.')

    parser.add_argument('-F', '--logging_format', nargs='?', type=str, default=None,
                        help='The format for Python logging')
    parser.add_argument('-l', '--logging_level', nargs='?', type=int, default=None,
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

    parser.add_argument('-E', '--python_executable', nargs='?', type=str, default=None,
                        help='The Python executable')
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

    args = read_environments()
    args.update({k: v for k, v in vars(parser.parse_args()).items() if v is not None})

    # Set logging
    logging_format = args.pop('logging_format')
    logging_level = args.pop('logging_level')
    logging_filename = args.pop('logging_filename')

    logging.basicConfig(
        filename=logging_filename,
        format=logging_format,
        level=logging_level,
    )

    # Start CI
    bot_cd = BotCi(**args)
    bot_cd.run()
