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

        msg_create_virtualenv_fail=getenv(
            'MSG_CREATE_VIRTUALENV_FAIL',
            "Error during virtualenv creation for version %(version)s!"
        ),
        msg_install_requirements_fail=getenv(
            'MSG_INSTALL_REQUIREMENTS_FAIL',
            "Error during install requirements for version %(version)s!"
        ),
        msg_run_tests_fail=getenv(
            'MSG_RUN_TESTS_FAIL',
            "Error during tests run for version %(version)s!"
        ),
        msg_coverage_fail=getenv(
            'MSG_COVERAGE_FAIL',
            "Error during get coverage run for version %(version)s!"
        ),
        msg_coverage_low=getenv(
            'MSG_COVERAGE_LOW',
            "Coverage too low for version %(version)s!"
        ),
        msg_restart_fail=getenv(
            'MSG_RESTART_FAIL',
            "Error during bot restart for version %(version)s!"
        ),
        msg_new_version=getenv(
            'MSG_NEW_VERSION',
            "I'm at new version %(version)s!"
        ),

        pid_file_path=getenv('PID_FILE_PATH'),

        python_executable=getenv('PYTHON_EXECUTABLE'),
        virtualenv_path=getenv('VIRTUALENV_PATH', '.virtualenv'),
        create_virtualenv=getenv('CREATE_VIRTUALENV'),

        requirements_path=getenv('REQUIREMENTS_PATH'),
        install_requirements=getenv('INSTALL_REQUIREMENTS'),

        run_tests=getenv('RUN_TESTS'),
        get_coverage_percentage=getenv('GET_COVERAGE_PERCENTAGE'),
        min_coverage=getenv('MIN_COVERAGE', 100, parser=int),

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

            msg_create_virtualenv_fail=None,
            msg_install_requirements_fail=None,
            msg_run_tests_fail=None,
            msg_coverage_fail=None,
            msg_coverage_low=None,
            msg_restart_fail=None,
            msg_new_version=None,

            pid_file_path=None,

            python_executable=None,
            virtualenv_path=None,
            create_virtualenv=None,

            requirements_path=None,
            install_requirements=None,

            run_tests=None,
            skip_tests=False,
            get_coverage_percentage=None,
            skip_coverage=False,
            min_coverage=0,

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

        self.msg_create_virtualenv_fail = msg_create_virtualenv_fail
        self.msg_install_requirements_fail = msg_install_requirements_fail
        self.msg_run_tests_fail = msg_run_tests_fail
        self.msg_coverage_fail = msg_coverage_fail
        self.msg_coverage_low = msg_coverage_low
        self.msg_restart_fail = msg_restart_fail
        self.msg_new_version = msg_new_version

        # pid file
        self.pid_file_path = pid_file_path or os.path.join(self.repo_path, '.pid')

        self.force = force

        # Virtualenv
        self.python_executable = python_executable or 'python3'
        self.virtualenv_path = virtualenv_path
        self.bin_path = os.path.join(self.virtualenv_path, 'bin') if self.virtualenv_path else None
        self.create_virtualenv = None
        if create_virtualenv:
            self.create_virtualenv = create_virtualenv
        elif self.virtualenv_path:
            self.create_virtualenv = 'virtualenv %s -p %s' % (
                self.virtualenv_path, self.python_executable
            )

        # Requirements
        self.requirements_path = requirements_path or 'requirements.txt'
        self.install_requirements = install_requirements if install_requirements else '%s install -r %s' % (
            os.path.join(self.bin_path or '', 'pip'), self.requirements_path
        )

        # Tests
        self.run_tests = run_tests if run_tests else '%s --cov=bot' % os.path.join(self.bin_path or '', 'pytest')
        self.skip_tests = skip_tests

        # Coverage percentage
        self.get_coverage_percentage = get_coverage_percentage if get_coverage_percentage else (
            '%s report | grep TOTAL | awk \'{print $(NF)}\' | sed \'s/.$//\'' %
            os.path.join(self.bin_path or '', 'coverage')
        )
        self.skip_coverage = skip_coverage
        self.min_coverage = min_coverage

        # Run
        self.run_bot = run_bot if run_bot else '%s %s' % (os.path.join(self.bin_path or '', 'python'), 'bot.py')

        # True when local branch does not exist
        self.tags_map = {}

        # The pid of the daemon process
        self.pid = None

        # Versions name
        self.old_version = None
        self.version = None

        self.coverage = None

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
        if self.create_virtualenv and self.virtualenv_path:
            if not os.path.exists(os.path.join(self.repo_path, self.virtualenv_path)):
                logger.info('Create virtualenv: %s' % self.create_virtualenv)
                process = subprocess.Popen(self.create_virtualenv, cwd=self.repo_path, shell=True)
                return process.wait()
            else:
                logger.info('Virtualenv %s already exist' % self.virtualenv_path)
        return 0

    def call_install_requirements(self):
        """Install requirements"""
        logger.info('Install requirements: %s' % self.install_requirements)
        process = subprocess.Popen(self.install_requirements, cwd=self.repo_path, shell=True)
        return process.wait()

    def call_run_tests(self):
        """Run tests"""
        if not self.skip_tests:
            logger.info('Run tests: %s' % self.run_tests)
            process = subprocess.Popen(self.run_tests, cwd=self.repo_path, shell=True)
            return process.wait()
        return 0

    def call_get_coverage_percentage(self):
        """Get coverage percentage"""
        if not self.skip_tests and not self.skip_coverage:
            logger.info('Run get coverage percentage: %s' % self.get_coverage_percentage)
            process = subprocess.Popen(
                self.get_coverage_percentage,
                cwd=self.repo_path,
                shell=True,
                stdout=subprocess.PIPE,
            )
            returncode = process.wait()
            if not returncode:
                try:
                    self.coverage = float(process.stdout.read())
                except ValueError:
                    return 'Invalid format'
            return returncode
        return 0

    def stop_bot(self):
        """Stop running bot"""
        # Check pid file
        if os.path.exists(self.pid_file_path):
            logger.info('Stop started bot')
            try:
                with open(self.pid_file_path, 'r') as f:
                    pid = int(f.read())
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except OSError:
                logger.info('Process already stopped')
        return 0

    def start_bot(self):
        """Start the bot"""
        # Run bot
        logger.info('Run bot %s: %s' % (self.version, self.run_bot))
        process = subprocess.Popen(self.run_bot, cwd=self.repo_path, shell=True)
        self.pid = process.pid

        # Save pid
        logger.info('Save pid %s' % self.pid)
        with open(self.pid_file_path, 'w') as f:
            f.write(str(self.pid))
        return 0

    def restart_bot(self):
        """Stop and restart the bot"""
        return self.stop_bot() or self.start_bot()

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

    def get_context(self):
        return {
            'old_version': self.old_version,
            'version': self.version,
            'author': self.author,
            'min_coverage': self.min_coverage,
            'coverage': self.coverage,
        }

    def send_create_virtualenv_fail_message(self):
        """Send a message when create virtualenv fail"""
        if self.msg_create_virtualenv_fail:
            self.send_message(self.msg_create_virtualenv_fail % self.get_context())

    def send_install_requirements_fail_message(self):
        """Send a message when install requirements fail"""
        if self.msg_install_requirements_fail:
            self.send_message(self.msg_install_requirements_fail % self.get_context())

    def send_run_tests_fail_message(self):
        """Send a message when run tests fail"""
        if self.msg_run_tests_fail:
            self.send_message(self.msg_run_tests_fail % self.get_context())

    def send_get_coverage_fail_message(self):
        """Send a message when get coverage fail"""
        if self.msg_coverage_fail:
            self.send_message(self.msg_coverage_fail % self.get_context())

    def send_low_coverage_fail_message(self):
        """Send a message when coverage is too low"""
        if self.msg_coverage_low:
            self.send_message(self.msg_coverage_low % self.get_context())

    def send_restart_fail_message(self):
        """Send a message when bot restart fail"""
        if self.msg_restart_fail:
            self.send_message(self.msg_restart_fail % self.get_context())

    def send_new_version_message(self):
        """Send a message when new version was deployed"""
        if self.msg_new_version:
            self.send_message(self.msg_new_version % self.get_context())

    def clone_repo(self):
        """Clone repo if need"""
        if self.is_new_repo:
            logger.info('Clone repo %s to %s' % (self.repo_url, self.repo_path))
            Repo.clone_from(self.repo_url, self.repo_path, env={'GIT_SSH_COMMAND': self.ssh_cmd})

    def release_flow(self):
        # Release
        if self.call_create_virtualenv():
            self.send_create_virtualenv_fail_message()
            self.error('Virtualenv not created')

        if self.call_install_requirements():
            self.send_install_requirements_fail_message()
            self.error('Requirements not installed')

        if self.call_run_tests():
            self.send_run_tests_fail_message()
            self.error('Test error')

        if self.call_get_coverage_percentage():
            self.send_get_coverage_fail_message()
            self.error('Missing coverage percentage')

        if self.coverage is not None and self.coverage < self.min_coverage:
            self.send_low_coverage_fail_message()
            self.error('Coverage percentage (%s%%) too low' % self.coverage)

        if self.restart_bot():
            self.send_restart_fail_message()
            self.error('Bot not restared')

        self.send_new_version_message()

    def run(self):
        # Clone repo if need
        self.clone_repo()

        # Init repo
        logger.info('Init repo %s' % self.repo_path)
        repo = Repo.init(self.repo_path)

        # Set old version
        self.old_version = repo.git.describe('--always')
        logger.info('Old version %s' % self.old_version)

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

            logger.info('New version %s by %s' % (self.version, self.author))

            if self.last_tag.tag.object != repo.head.commit or self.force:
                logger.info('Reset to HEAD')

                # Go to last tag
                repo.head.reset(self.last_tag, index=True, working_tree=True)

                self.release_flow()
            else:
                logger.info('Repo up to date on %s' % self.version)
        else:
            logger.info('No tags on branch %s' % self.branch)


def main():
    parser = argparse.ArgumentParser(description='Test and deploy a telegram bot.')

    parser.add_argument('--logging_format', nargs='?', type=str, default=None,
                        help='The format for Python logging')
    parser.add_argument('--logging_level', nargs='?', type=int, default=None,
                        help='The level for Python logging')
    parser.add_argument('--logging_filename', nargs='?', type=str, default=None,
                        help='The filename for Python logging')

    parser.add_argument('-u', '--repo_url', nargs='?', type=str, default=None,
                        help='The URL of the repo to be used')
    parser.add_argument('-p', '--repo_path', nargs='?', type=str, default=None,
                        help='The local path of the repo')
    parser.add_argument('-b', '--branch', nargs='?', type=str, default=None,
                        help='The branch used for deploy')

    parser.add_argument('-F', '--force', action='store_true',
                        help='Restart also same versions')

    parser.add_argument('--ssh_key', nargs='?', type=str, default=None,
                        help='The SSH key to be used to authenticate to the repo')

    parser.add_argument('--chat_id', nargs='?', type=str, default=None,
                        help='The chat ID used for bot communication')
    parser.add_argument('--bot_token', nargs='?', type=str, default=None,
                        help='The bot token used for bot communication')

    parser.add_argument('--pid_file_path', nargs='?', type=str, default=None,
                        help='The path to the PID file')

    parser.add_argument('--python_executable', nargs='?', type=str, default=None,
                        help='The Python executable')
    parser.add_argument('--virtualenv_path', nargs='?', type=str, default=None,
                        help='The path to the Python virtualenv')
    parser.add_argument('--create_virtualenv', nargs='?', type=str, default=None,
                        help='The command used in order to create the Python virtualenv')

    parser.add_argument('--requirements_path', nargs='?', type=str, default=None,
                        help='The path to the requirements file')
    parser.add_argument('--install_requirements', nargs='?', type=str, default=None,
                        help='The command used in order to install the requirements')

    parser.add_argument('--run_tests', nargs='?', type=str, default=None,
                        help='The command used in order to run the tests')
    parser.add_argument('-t', '--skip_tests', action='store_true',
                        help='Skip tests')

    parser.add_argument('--get_coverage_percentage', nargs='?', type=str, default=None,
                        help='The command used in order to get the coverage percentage value')
    parser.add_argument('-c', '--skip_coverage', action='store_true',
                        help='Skip coverage check')
    parser.add_argument('--min_coverage', nargs='?', type=int, default=None,
                        help='The minimal coverage required in order to deploy')

    parser.add_argument('--run_bot', nargs='?', type=str, default=None,
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
