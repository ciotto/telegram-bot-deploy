import signal

import logging
import string
import os
import random
import sys
import unittest
import uuid

import telegram
import tempfile
from git import Repo

from bot_ci import main, BotCi, read_environments

if sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 6):
    import mock
else:
    from unittest import mock


class FakeAuthor(object):
    def __init__(self, name=None, email=None):
        self.name = name or 'foo'
        self.author = email or 'bar@asd.com'


class FakeObject(object):
    def __init__(self, hexsha=None):
        self.hexsha = hexsha or uuid.uuid4().hex

    def __str__(self):
        return self.hexsha


class FakeCommit(FakeObject):
    def __init__(self, parents=None, author=None, **kwargs):
        super(FakeCommit, self).__init__(**kwargs)
        self.parents = parents or []
        self.author = author or FakeAuthor()


class FakeRef(object):
    def __init__(self, object, path):
        self.object = object
        self.path = path

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.path

    @property
    def commit(self):
        return self.object


class FakeTagRef(FakeRef):
    def __init__(self, object, *args, **kwargs):
        super(FakeTagRef, self).__init__(object, *args, **kwargs)

        self.object = FakeTag(object, self.name)

    @property
    def name(self):
        return self.path.split('/')[-1]

    @property
    def tag(self):
        return self.object


class FakeTag(FakeObject):
    def __init__(self, object, tag):
        super(FakeTag, self).__init__()
        self.object = object
        self.tag = tag


def get_random_path():
    return os.path.join(
        tempfile.gettempdir(),
        ''.join(random.choice(string.ascii_lowercase) for i in range(10))
    )


def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)


class TestCI(unittest.TestCase):
    def test_init(self):
        with mock.patch.object(BotCi, 'check') as check_mock:
            bot_ci = BotCi()

            self.assertEqual(bot_ci.repo_url, None)
            self.assertEqual(bot_ci.repo_path, 'repo')
            self.assertEqual(bot_ci.branch, None)
            self.assertEqual(bot_ci.ssh_key, None)
            self.assertEqual(bot_ci.ssh_cmd, None)
            self.assertEqual(bot_ci.chat_id, None)
            self.assertEqual(bot_ci.bot_token, None)
            self.assertIsNone(bot_ci.bot)
            self.assertEqual(bot_ci.msg_create_virtualenv_fail, None)
            self.assertEqual(bot_ci.msg_install_requirements_fail, None)
            self.assertEqual(bot_ci.msg_run_tests_fail, None)
            self.assertEqual(bot_ci.msg_coverage_fail, None)
            self.assertEqual(bot_ci.msg_coverage_low, None)
            self.assertEqual(bot_ci.msg_restart_fail, None)
            self.assertEqual(bot_ci.msg_new_version, None)
            self.assertEqual(bot_ci.pid_file_path, os.path.join('repo', '.pid'))
            self.assertEqual(bot_ci.force, False)
            self.assertEqual(bot_ci.python_executable, 'python3')
            self.assertEqual(bot_ci.virtualenv_path, None)
            self.assertEqual(bot_ci.bin_path, None)
            self.assertEqual(bot_ci.create_virtualenv, None)
            self.assertEqual(bot_ci.requirements_path, 'requirements.txt')
            self.assertEqual(bot_ci.install_requirements, [
                'pip', 'install', '-r', 'requirements.txt'
            ])
            self.assertEqual(bot_ci.run_tests, [
                'pytest', '--cov=bot'
            ])
            self.assertEqual(bot_ci.skip_tests, False)
            self.assertEqual(bot_ci.get_coverage_percentage, [
                "coverage", "report", "|", "tail", "-1", "|", "awk", "'{print $(NF)}'", "|", "sed", "'s/.$//'"
            ])
            self.assertEqual(bot_ci.skip_coverage, False)
            self.assertEqual(bot_ci.min_coverage, 0)
            self.assertEqual(bot_ci.run_bot, [
                'python', 'bot.py'
            ])
            self.assertEqual(bot_ci.tags_map, {})
            self.assertEqual(bot_ci.pid, None)
            self.assertEqual(bot_ci.old_version, None)
            self.assertEqual(bot_ci.version, None)
            self.assertEqual(bot_ci.coverage, None)
            self.assertEqual(bot_ci.remote_commit, None)
            self.assertEqual(bot_ci.last_tag, None)
            self.assertEqual(bot_ci.author, None)

            check_mock.assert_called_once_with()

    def test_init_read_environments(self):
        with mock.patch('bot_ci.load_dotenv') as load_dotenv_mock, \
                mock.patch.object(BotCi, 'check') as check_mock:
            bot_ci = BotCi(**read_environments())

            self.assertEqual(bot_ci.repo_url, None)
            self.assertEqual(bot_ci.repo_path, 'repo')
            self.assertEqual(bot_ci.branch, 'master')
            self.assertEqual(bot_ci.ssh_key, os.path.abspath('id_deployment_key'))
            self.assertEqual(bot_ci.ssh_cmd, 'ssh -i %s' % os.path.abspath('id_deployment_key'))
            self.assertEqual(bot_ci.chat_id, None)
            self.assertEqual(bot_ci.bot_token, None)
            self.assertIsNone(bot_ci.bot)
            self.assertEqual(
                bot_ci.msg_create_virtualenv_fail,
                "Error during virtualenv creation for version %(version)s!"
            )
            self.assertEqual(
                bot_ci.msg_install_requirements_fail,
                "Error during install requirements for version %(version)s!"
            )
            self.assertEqual(
                bot_ci.msg_run_tests_fail,
                "Error during tests run for version %(version)s!"
            )
            self.assertEqual(
                bot_ci.msg_coverage_fail,
                "Error during get coverage run for version %(version)s!"
            )
            self.assertEqual(
                bot_ci.msg_coverage_low,
                "Coverage too low for version %(version)s!"
            )
            self.assertEqual(
                bot_ci.msg_restart_fail,
                "Error during bot restart for version %(version)s!"
            )
            self.assertEqual(
                bot_ci.msg_new_version,
                "I'm at new version %(version)s!"
            )
            self.assertEqual(bot_ci.pid_file_path, os.path.join('repo', '.pid'))
            self.assertEqual(bot_ci.force, False)
            self.assertEqual(bot_ci.python_executable, 'python3')
            self.assertEqual(bot_ci.virtualenv_path, '.virtualenv')
            self.assertEqual(bot_ci.bin_path, os.path.join('.virtualenv', 'bin'))
            self.assertEqual(bot_ci.create_virtualenv, [
                'virtualenv', '.virtualenv', '--no-site-packages', '-p', 'python3'
            ])
            self.assertEqual(bot_ci.requirements_path, 'requirements.txt')
            self.assertEqual(bot_ci.install_requirements, [
                os.path.join('.virtualenv', 'bin', 'pip'), 'install', '-r', 'requirements.txt'
            ])
            self.assertEqual(bot_ci.run_tests, [
                os.path.join('.virtualenv', 'bin', 'pytest'), '--cov=bot'
            ])
            self.assertEqual(bot_ci.skip_tests, False)
            self.assertEqual(bot_ci.get_coverage_percentage, [
                os.path.join('.virtualenv', 'bin', 'coverage'), "report", "|", "tail", "-1", "|", "awk",
                "'{print $(NF)}'", "|", "sed", "'s/.$//'"
            ])
            self.assertEqual(bot_ci.skip_coverage, False)
            self.assertEqual(bot_ci.min_coverage, 100)
            self.assertEqual(bot_ci.run_bot, [
                os.path.join('.virtualenv', 'bin', 'python'), 'bot.py'
            ])
            self.assertEqual(bot_ci.tags_map, {})
            self.assertEqual(bot_ci.pid, None)
            self.assertEqual(bot_ci.old_version, None)
            self.assertEqual(bot_ci.version, None)
            self.assertEqual(bot_ci.coverage, None)
            self.assertEqual(bot_ci.remote_commit, None)
            self.assertEqual(bot_ci.last_tag, None)
            self.assertEqual(bot_ci.author, None)

            load_dotenv_mock.assert_called_once()
            check_mock.assert_called_once_with()

    def test_init_args(self):
        with mock.patch('bot_ci.load_dotenv') as load_dotenv_mock, \
                mock.patch.object(BotCi, 'check') as check_mock:
            args = read_environments()
            args.update(dict(
                create_virtualenv='python3 -m venv .virtualenv',
                install_requirements='.virtualenv/bin/pip install repo',
                run_tests='.virtualenv/bin/python -m test',
                run_bot='.virtualenv/bin/python -m bot',
                get_coverage_percentage='.virtualenv/bin/coverage foo bar'
            ))
            bot_ci = BotCi(**args)

            self.assertEqual(bot_ci.repo_url, None)
            self.assertEqual(bot_ci.repo_path, 'repo')
            self.assertEqual(bot_ci.branch, 'master')
            self.assertEqual(bot_ci.ssh_key, os.path.abspath('id_deployment_key'))
            self.assertEqual(bot_ci.ssh_cmd, 'ssh -i %s' % os.path.abspath('id_deployment_key'))
            self.assertEqual(bot_ci.chat_id, None)
            self.assertEqual(bot_ci.bot_token, None)
            self.assertIsNone(bot_ci.bot)
            self.assertEqual(
                bot_ci.msg_create_virtualenv_fail,
                "Error during virtualenv creation for version %(version)s!"
            )
            self.assertEqual(
                bot_ci.msg_install_requirements_fail,
                "Error during install requirements for version %(version)s!"
            )
            self.assertEqual(
                bot_ci.msg_run_tests_fail,
                "Error during tests run for version %(version)s!"
            )
            self.assertEqual(
                bot_ci.msg_restart_fail,
                "Error during bot restart for version %(version)s!"
            )
            self.assertEqual(
                bot_ci.msg_new_version,
                "I'm at new version %(version)s!"
            )
            self.assertEqual(bot_ci.pid_file_path, os.path.join('repo', '.pid'))
            self.assertEqual(bot_ci.force, False)
            self.assertEqual(bot_ci.python_executable, 'python3')
            self.assertEqual(bot_ci.virtualenv_path, '.virtualenv')
            self.assertEqual(bot_ci.bin_path, os.path.join('.virtualenv', 'bin'))
            self.assertEqual(bot_ci.create_virtualenv, [
                'python3', '-m', 'venv', '.virtualenv'
            ])
            self.assertEqual(bot_ci.requirements_path, 'requirements.txt')
            self.assertEqual(bot_ci.install_requirements, [
                '.virtualenv/bin/pip', 'install', 'repo'
            ])
            self.assertEqual(bot_ci.run_tests, [
                '.virtualenv/bin/python', '-m', 'test'
            ])
            self.assertEqual(bot_ci.skip_tests, False)
            self.assertEqual(bot_ci.get_coverage_percentage, [
                '.virtualenv/bin/coverage', 'foo', 'bar'
            ])
            self.assertEqual(bot_ci.skip_coverage, False)
            self.assertEqual(bot_ci.min_coverage, 100)
            self.assertEqual(bot_ci.run_bot, [
                '.virtualenv/bin/python', '-m', 'bot'
            ])
            self.assertEqual(bot_ci.tags_map, {})
            self.assertEqual(bot_ci.pid, None)
            self.assertEqual(bot_ci.old_version, None)
            self.assertEqual(bot_ci.version, None)
            self.assertEqual(bot_ci.coverage, None)
            self.assertEqual(bot_ci.remote_commit, None)
            self.assertEqual(bot_ci.last_tag, None)
            self.assertEqual(bot_ci.author, None)

            load_dotenv_mock.assert_called_once()
            check_mock.assert_called_once_with()

    def test_init_args_commands(self):
        with mock.patch.object(BotCi, 'check') as check_mock:
            bot_ci = BotCi(
                repo_url='git@github.com:foo/bar.git',
                repo_path='path/to/local/repo',
                branch='dev',
                ssh_key='/etc/my_ssh_key',
                chat_id=-123123,
                bot_token='111111111:AAA-AA-AAAAAAAAAAAAAAAAAAAAAAAAAAAA',
                msg_create_virtualenv_fail='Version %(version)s!',
                msg_install_requirements_fail='Version %(version)s!',
                msg_run_tests_fail='Version %(version)s!',
                msg_coverage_fail='Version %(version)s!',
                msg_coverage_low='Version %(version)s!',
                msg_restart_fail='Version %(version)s!',
                msg_new_version='Version %(version)s!',
                pid_file_path='mypidfile',
                force=True,
                python_executable='/usr/local/bin/python2.7',
                virtualenv_path='my/virtualenv/path',
                requirements_path='path/to/requirements.txt',
                skip_tests=True,
                skip_coverage=True,
                min_coverage=50,
            )

            self.assertEqual(bot_ci.repo_url, 'git@github.com:foo/bar.git')
            self.assertEqual(bot_ci.repo_path, 'path/to/local/repo')
            self.assertEqual(bot_ci.branch, 'dev')
            self.assertEqual(bot_ci.ssh_key, '/etc/my_ssh_key')
            self.assertEqual(bot_ci.ssh_cmd, 'ssh -i /etc/my_ssh_key')
            self.assertEqual(bot_ci.chat_id, -123123)
            self.assertEqual(bot_ci.bot_token, '111111111:AAA-AA-AAAAAAAAAAAAAAAAAAAAAAAAAAAA')
            self.assertIsNotNone(bot_ci.bot)
            self.assertEqual(bot_ci.msg_create_virtualenv_fail, 'Version %(version)s!')
            self.assertEqual(bot_ci.msg_install_requirements_fail, 'Version %(version)s!')
            self.assertEqual(bot_ci.msg_run_tests_fail, 'Version %(version)s!')
            self.assertEqual(bot_ci.msg_coverage_fail, 'Version %(version)s!')
            self.assertEqual(bot_ci.msg_coverage_low, 'Version %(version)s!')
            self.assertEqual(bot_ci.msg_restart_fail, 'Version %(version)s!')
            self.assertEqual(bot_ci.msg_new_version, 'Version %(version)s!')
            self.assertEqual(bot_ci.pid_file_path, 'mypidfile')
            self.assertEqual(bot_ci.force, True)
            self.assertEqual(bot_ci.python_executable, '/usr/local/bin/python2.7')
            self.assertEqual(bot_ci.virtualenv_path, 'my/virtualenv/path')
            self.assertEqual(bot_ci.bin_path, os.path.join('my/virtualenv/path', 'bin'))
            self.assertEqual(bot_ci.create_virtualenv, [
                'virtualenv', 'my/virtualenv/path', '--no-site-packages', '-p', '/usr/local/bin/python2.7'
            ])
            self.assertEqual(bot_ci.requirements_path, 'path/to/requirements.txt')
            self.assertEqual(bot_ci.install_requirements, [
                os.path.join('my/virtualenv/path', 'bin', 'pip'), 'install', '-r', 'path/to/requirements.txt'
            ])
            self.assertEqual(bot_ci.run_tests, [
                os.path.join('my/virtualenv/path', 'bin', 'pytest'), '--cov=bot'
            ])
            self.assertEqual(bot_ci.skip_tests, True)
            self.assertEqual(bot_ci.get_coverage_percentage, [
                os.path.join('my/virtualenv/path', 'bin', 'coverage'), "report", "|", "tail", "-1", "|", "awk",
                "'{print $(NF)}'", "|", "sed", "'s/.$//'"
            ])
            self.assertEqual(bot_ci.skip_coverage, True)
            self.assertEqual(bot_ci.min_coverage, 50)
            self.assertEqual(bot_ci.run_bot, [
                os.path.join('my/virtualenv/path', 'bin', 'python'), 'bot.py'
            ])
            self.assertEqual(bot_ci.tags_map, {})
            self.assertEqual(bot_ci.pid, None)
            self.assertEqual(bot_ci.old_version, None)
            self.assertEqual(bot_ci.version, None)
            self.assertEqual(bot_ci.coverage, None)
            self.assertEqual(bot_ci.remote_commit, None)
            self.assertEqual(bot_ci.last_tag, None)
            self.assertEqual(bot_ci.author, None)

            check_mock.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_error(self, *args):
        bot_ci = BotCi()

        with mock.patch('bot_ci.logger.error') as error_mock, \
                mock.patch('os._exit') as _exit_mock:
            bot_ci.error('My message')

            error_mock.assert_called_once_with('My message')
            _exit_mock.assert_called_once_with(os.EX_IOERR)

    @mock.patch.object(BotCi, 'check')
    def test_error_code(self, *args):
        bot_ci = BotCi()

        with mock.patch('bot_ci.logger.error') as error_mock, \
                mock.patch('os._exit') as _exit_mock:
            bot_ci.error('My message', code=42)

            error_mock.assert_called_once_with('My message')
            _exit_mock.assert_called_once_with(42)

    def test_check(self, *args):
        with mock.patch.object(BotCi, 'check'):
            bot_ci = BotCi()

        with mock.patch.object(BotCi, 'error') as error_mock:
            bot_ci.check()

            error_mock.assert_called_once_with('Missing repo_url', code=os.EX_DATAERR)

    def test_check_ok(self, *args):
        with mock.patch.object(BotCi, 'check'):
            bot_ci = BotCi(repo_url='foo')

        with mock.patch.object(BotCi, 'error') as error_mock:
            bot_ci.check()

            error_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_is_new_repo(self, *args):
        bot_ci = BotCi(repo_path=get_random_path())

        # Folder does not exists
        self.assertTrue(bot_ci.is_new_repo)

        # Folder exists
        os.mkdir(bot_ci.repo_path)
        self.assertFalse(bot_ci.is_new_repo)

    @mock.patch.object(BotCi, 'check')
    def test_get_last_tag(self, *args):
        c1 = FakeCommit()
        c2 = FakeCommit([c1])
        c3 = FakeCommit([c2])
        c3b = FakeCommit([c2])
        c4 = FakeCommit([c3, c3b])
        c5 = FakeCommit([c4])

        bot_ci = BotCi()

        # Check empty tags_map
        self.assertEqual(bot_ci.get_last_tag(c1), None)

        bot_ci.tags_map = {
            c2: FakeTagRef(path='v1', object=c2),
            c4: FakeTagRef(path='v2', object=c4),
        }

        # Check w/ tags_map
        self.assertEqual(bot_ci.get_last_tag(c5).name, 'v2')
        self.assertEqual(bot_ci.get_last_tag(c4).name, 'v2')
        self.assertEqual(bot_ci.get_last_tag(c3).name, 'v1')
        self.assertEqual(bot_ci.get_last_tag(c3b).name, 'v1')
        self.assertEqual(bot_ci.get_last_tag(c2).name, 'v1')
        self.assertEqual(bot_ci.get_last_tag(c1), None)

    @mock.patch.object(BotCi, 'check')
    def test_call_create_virtualenv(self, *args):
        bot_ci = BotCi(virtualenv_path=get_random_path())

        popen = mock.Mock()
        popen.wait.return_value = 0
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_create_virtualenv(), 0)

            popen_mock.assert_called_once_with(bot_ci.create_virtualenv, cwd=bot_ci.repo_path)
            popen.wait.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_call_create_virtualenv_error(self, *args):
        bot_ci = BotCi(virtualenv_path=get_random_path())

        popen = mock.Mock()
        popen.wait.return_value = 1
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_create_virtualenv(), 1)

            popen_mock.assert_called_once_with(bot_ci.create_virtualenv, cwd=bot_ci.repo_path)
            popen.wait.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_call_create_virtualenv_exists(self, *args):
        bot_ci = BotCi(virtualenv_path=get_random_path())
        os.mkdir(bot_ci.virtualenv_path)

        popen = mock.Mock()
        popen.wait.return_value = 0
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_create_virtualenv(), 0)

            popen_mock.assert_not_called()
            popen.wait.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_call_create_virtualenv_no_virtualenv(self, *args):
        bot_ci = BotCi()

        popen = mock.Mock()
        popen.wait.return_value = 0
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_create_virtualenv(), 0)

            popen_mock.assert_not_called()
            popen.wait.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_call_install_requirements(self, *args):
        bot_ci = BotCi()

        popen = mock.Mock()
        popen.wait.return_value = 0
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_install_requirements(), 0)

            popen_mock.assert_called_once_with(bot_ci.install_requirements, cwd=bot_ci.repo_path)
            popen.wait.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_call_install_requirements_error(self, *args):
        bot_ci = BotCi()

        popen = mock.Mock()
        popen.wait.return_value = 1
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_install_requirements(), 1)

            popen_mock.assert_called_once_with(bot_ci.install_requirements, cwd=bot_ci.repo_path)
            popen.wait.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_call_run_tests(self, *args):
        bot_ci = BotCi(skip_tests=False)

        popen = mock.Mock()
        popen.wait.return_value = 0
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_run_tests(), 0)

            popen_mock.assert_called_once_with(bot_ci.run_tests, cwd=bot_ci.repo_path)
            popen.wait.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_call_run_tests_error(self, *args):
        bot_ci = BotCi(skip_tests=False)

        popen = mock.Mock()
        popen.wait.return_value = 1
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_run_tests(), 1)

            popen_mock.assert_called_once_with(bot_ci.run_tests, cwd=bot_ci.repo_path)
            popen.wait.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_call_run_tests_skip(self, *args):
        bot_ci = BotCi(skip_tests=True)

        popen = mock.Mock()
        popen.wait.return_value = 0
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_run_tests(), 0)

            popen_mock.assert_not_called()
            popen.wait.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_call_get_coverage_percentage(self, *args):
        bot_ci = BotCi(skip_tests=False)

        popen = mock.Mock()
        popen.wait.return_value = 0
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_get_coverage_percentage(), 0)

            popen_mock.assert_called_once_with(bot_ci.get_coverage_percentage, cwd=bot_ci.repo_path)
            popen.wait.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_call_get_coverage_percentage_error(self, *args):
        bot_ci = BotCi(skip_tests=False)

        popen = mock.Mock()
        popen.wait.return_value = 1
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_get_coverage_percentage(), 1)

            popen_mock.assert_called_once_with(bot_ci.get_coverage_percentage, cwd=bot_ci.repo_path)
            popen.wait.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_call_get_coverage_percentage_skip(self, *args):
        bot_ci = BotCi(skip_coverage=True)

        popen = mock.Mock()
        popen.wait.return_value = 0
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_get_coverage_percentage(), 0)

            popen_mock.assert_not_called()
            popen.wait.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_call_get_coverage_percentage_skip_test(self, *args):
        bot_ci = BotCi(skip_tests=True)

        popen = mock.Mock()
        popen.wait.return_value = 0
        with mock.patch('subprocess.Popen', return_value=popen) as popen_mock:
            self.assertEqual(bot_ci.call_get_coverage_percentage(), 0)

            popen_mock.assert_not_called()
            popen.wait.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_stop_bot(self, *args):
        bot_ci = BotCi(pid_file_path=get_random_path())
        write_file(bot_ci.pid_file_path, '123123')

        with mock.patch('bot_ci.os.kill') as kill_mock:
            bot_ci.stop_bot()

            kill_mock.assert_called_once_with(123123, signal.SIGTERM)

    @mock.patch.object(BotCi, 'check')
    def test_stop_bot_stopped(self, *args):
        bot_ci = BotCi(pid_file_path=get_random_path())
        write_file(bot_ci.pid_file_path, '123123')

        with mock.patch('bot_ci.os.kill') as kill_mock:
            kill_mock.side_effect = OSError

            bot_ci.stop_bot()

            kill_mock.assert_called()

    @mock.patch.object(BotCi, 'check')
    def test_stop_bot_not_exists(self, *args):
        bot_ci = BotCi(pid_file_path=get_random_path())

        with mock.patch('bot_ci.os.kill') as kill_mock:
            bot_ci.stop_bot()

            kill_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_start_bot(self, *args):
        bot_ci = BotCi(pid_file_path=get_random_path())

        with mock.patch('subprocess.Popen') as popen_mock:
            bot_ci.start_bot()

            self.assertTrue(os.path.exists(bot_ci.pid_file_path))

            popen_mock.assert_called_once_with(bot_ci.run_bot, cwd=bot_ci.repo_path)

    @mock.patch.object(BotCi, 'check')
    def test_restart_bot(self, *args):
        bot_ci = BotCi(pid_file_path=get_random_path())

        with mock.patch.object(BotCi, 'stop_bot', return_value=0) as stop_bot_mock, \
                mock.patch.object(BotCi, 'start_bot', return_value=0) as start_bot_mock:
            self.assertFalse(bot_ci.restart_bot())

            stop_bot_mock.assert_called_once_with()
            start_bot_mock.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_restart_bot_error(self, *args):
        bot_ci = BotCi(pid_file_path=get_random_path())

        with mock.patch.object(BotCi, 'stop_bot', return_value=1) as stop_bot_mock, \
                mock.patch.object(BotCi, 'start_bot', return_value=0) as start_bot_mock:
            self.assertTrue(bot_ci.restart_bot())

            stop_bot_mock.assert_called_once_with()
            start_bot_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    @mock.patch.object(telegram.Bot, '_validate_token')
    def test_send_message(self, *args):
        bot_ci = BotCi(bot_token='mytoken', chat_id=123123)

        with mock.patch.object(telegram.Bot, 'send_message') as send_message_mock:
            bot_ci.send_message('My message')

            send_message_mock.assert_called_once_with(chat_id=123123, text='My message')

    @mock.patch.object(BotCi, 'check')
    def test_send_message_no_bot(self, *args):
        bot_ci = BotCi()

        with mock.patch.object(telegram.Bot, 'send_message') as send_message_mock:
            bot_ci.send_message('My message')

            send_message_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    @mock.patch.object(telegram.Bot, '_validate_token')
    def test_send_message_no_chat_id(self, *args):
        bot_ci = BotCi(bot_token='mytoken')

        with mock.patch.object(telegram.Bot, 'send_message') as send_message_mock:
            bot_ci.send_message('My message')

            send_message_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_get_context(self, *args):
        bot_ci = BotCi()
        bot_ci.old_version = 'v1.0'
        bot_ci.version = 'v2.0'
        bot_ci.author = 'the author'
        bot_ci.min_coverage = 42
        bot_ci.coverage = 10

        self.assertEqual(
            bot_ci.get_context(),
            dict(
                old_version='v1.0',
                version='v2.0',
                author='the author',
                min_coverage=42,
                coverage=10,
            )
        )

    @mock.patch.object(BotCi, 'check')
    def test_send_create_virtualenv_fail_message(self, *args):
        bot_ci = BotCi(msg_create_virtualenv_fail='Version %(version)s by %(author)s, old version %(old_version)s')
        bot_ci.old_version = 'v1.0'
        bot_ci.version = 'v2.0'
        bot_ci.author = 'the author'

        with mock.patch.object(bot_ci, 'send_message') as send_message_mock:
            bot_ci.send_create_virtualenv_fail_message()

            send_message_mock.assert_called_once_with('Version v2.0 by the author, old version v1.0')

    @mock.patch.object(BotCi, 'check')
    def test_send_install_requirements_fail_message(self, *args):
        bot_ci = BotCi(msg_install_requirements_fail='Version %(version)s by %(author)s, old version %(old_version)s')
        bot_ci.old_version = 'v1.0'
        bot_ci.version = 'v2.0'
        bot_ci.author = 'the author'

        with mock.patch.object(bot_ci, 'send_message') as send_message_mock:
            bot_ci.send_install_requirements_fail_message()

            send_message_mock.assert_called_once_with('Version v2.0 by the author, old version v1.0')

    @mock.patch.object(BotCi, 'check')
    def test_send_run_tests_fail_message(self, *args):
        bot_ci = BotCi(msg_run_tests_fail='Version %(version)s by %(author)s, old version %(old_version)s')
        bot_ci.old_version = 'v1.0'
        bot_ci.version = 'v2.0'
        bot_ci.author = 'the author'

        with mock.patch.object(bot_ci, 'send_message') as send_message_mock:
            bot_ci.send_run_tests_fail_message()

            send_message_mock.assert_called_once_with('Version v2.0 by the author, old version v1.0')

    @mock.patch.object(BotCi, 'check')
    def test_send_get_coverage_fail_message(self, *args):
        bot_ci = BotCi(msg_coverage_fail='Version %(version)s by %(author)s, old version %(old_version)s')
        bot_ci.old_version = 'v1.0'
        bot_ci.version = 'v2.0'
        bot_ci.author = 'the author'

        with mock.patch.object(bot_ci, 'send_message') as send_message_mock:
            bot_ci.send_get_coverage_fail_message()

            send_message_mock.assert_called_once_with('Version v2.0 by the author, old version v1.0')

    @mock.patch.object(BotCi, 'check')
    def test_send_low_coverage_fail_message(self, *args):
        bot_ci = BotCi(msg_coverage_low='Version %(version)s by %(author)s, old version %(old_version)s')
        bot_ci.old_version = 'v1.0'
        bot_ci.version = 'v2.0'
        bot_ci.author = 'the author'

        with mock.patch.object(bot_ci, 'send_message') as send_message_mock:
            bot_ci.send_low_coverage_fail_message()

            send_message_mock.assert_called_once_with('Version v2.0 by the author, old version v1.0')

    @mock.patch.object(BotCi, 'check')
    def test_send_restart_fail_message(self, *args):
        bot_ci = BotCi(msg_restart_fail='Version %(version)s by %(author)s, old version %(old_version)s')
        bot_ci.old_version = 'v1.0'
        bot_ci.version = 'v2.0'
        bot_ci.author = 'the author'

        with mock.patch.object(bot_ci, 'send_message') as send_message_mock:
            bot_ci.send_restart_fail_message()

            send_message_mock.assert_called_once_with('Version v2.0 by the author, old version v1.0')

    @mock.patch.object(BotCi, 'check')
    def test_send_new_version_message(self, *args):
        bot_ci = BotCi(msg_new_version='Version %(version)s by %(author)s, old version %(old_version)s')
        bot_ci.old_version = 'v1.0'
        bot_ci.version = 'v2.0'
        bot_ci.author = 'the author'

        with mock.patch.object(bot_ci, 'send_message') as send_message_mock:
            bot_ci.send_new_version_message()

            send_message_mock.assert_called_once_with('Version v2.0 by the author, old version v1.0')

    @mock.patch.object(BotCi, 'check')
    def test_send_message_empty(self, *args):
        bot_ci = BotCi()

        with mock.patch.object(bot_ci, 'send_message') as send_message_mock:
            bot_ci.send_create_virtualenv_fail_message()
            bot_ci.send_install_requirements_fail_message()
            bot_ci.send_run_tests_fail_message()
            bot_ci.send_get_coverage_fail_message()
            bot_ci.send_low_coverage_fail_message()
            bot_ci.send_restart_fail_message()
            bot_ci.send_new_version_message()

            send_message_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_clone_repo(self, *args):
        bot_ci = BotCi(repo_path=get_random_path())

        with mock.patch.object(Repo, 'clone_from') as clone_from_mock:
            bot_ci.clone_repo()

            clone_from_mock.assert_called_once_with(
                bot_ci.repo_url,
                bot_ci.repo_path,
                env={'GIT_SSH_COMMAND': bot_ci.ssh_cmd}
            )

    @mock.patch.object(BotCi, 'check')
    def test_clone_repo_exists(self, *args):
        bot_ci = BotCi(
            repo_url='git@github.com:foo/bar.git',
            repo_path=get_random_path(),
        )
        os.mkdir(bot_ci.repo_path)

        with mock.patch.object(Repo, 'clone_from') as clone_from_mock:
            bot_ci.clone_repo()

            clone_from_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_release_flow(self, *args):
        def error(msg):
            self.fail('error() method called: %s' % msg)

        bot_ci = BotCi(repo_path=get_random_path(), branch='master', min_coverage=100)

        def set_coverage():
            bot_ci.coverage = 100

        with mock.patch.object(bot_ci, 'error', side_effect=error), \
                mock.patch.object(bot_ci, 'call_create_virtualenv', return_value=0) as call_create_virtualenv_mock, \
                mock.patch.object(bot_ci, 'call_install_requirements',
                                  return_value=0) as call_install_requirements_mock, \
                mock.patch.object(bot_ci, 'call_run_tests', return_value=0) as call_run_tests_mock, \
                mock.patch.object(bot_ci, 'call_get_coverage_percentage',
                                  return_value=0, side_effect=set_coverage) as call_get_coverage_percentage_mock, \
                mock.patch.object(bot_ci, 'restart_bot', return_value=0) as restart_bot_mock, \
                mock.patch.object(bot_ci, 'send_create_virtualenv_fail_message'
                                  ) as send_create_virtualenv_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_install_requirements_fail_message'
                                  ) as send_install_requirements_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_run_tests_fail_message'
                                  ) as send_run_tests_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_get_coverage_fail_message'
                                  ) as send_get_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_low_coverage_fail_message'
                                  ) as send_low_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_restart_fail_message'
                                  ) as send_restart_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_new_version_message'
                                  ) as send_new_version_message_mock:

            try:
                bot_ci.release_flow()
            except SystemExit:
                pass

            self.assertEqual(bot_ci.coverage, 100)

            # Check methods calls
            call_create_virtualenv_mock.assert_called_once_with()
            call_install_requirements_mock.assert_called_once_with()
            call_run_tests_mock.assert_called_once_with()
            call_get_coverage_percentage_mock.assert_called_once_with()
            restart_bot_mock.assert_called_once_with()
            send_create_virtualenv_fail_message_mock.assert_not_called()
            send_install_requirements_fail_message_mock.assert_not_called()
            send_run_tests_fail_message_mock.assert_not_called()
            send_get_coverage_fail_message_mock.assert_not_called()
            send_low_coverage_fail_message_mock.assert_not_called()
            send_restart_fail_message_mock.assert_not_called()
            send_new_version_message_mock.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_release_flow_fail_create_virtualenv(self, *args):
        bot_ci = BotCi(repo_path=get_random_path(), branch='master', min_coverage=100)

        with mock.patch.object(bot_ci, 'error', side_effect=SystemExit) as error_mock, \
                mock.patch.object(bot_ci, 'call_create_virtualenv', return_value=1) as call_create_virtualenv_mock, \
                mock.patch.object(bot_ci, 'call_install_requirements',
                                  return_value=0) as call_install_requirements_mock, \
                mock.patch.object(bot_ci, 'call_run_tests', return_value=0) as call_run_tests_mock, \
                mock.patch.object(bot_ci, 'call_get_coverage_percentage',
                                  return_value=0) as call_get_coverage_percentage_mock, \
                mock.patch.object(bot_ci, 'restart_bot', return_value=0) as restart_bot_mock, \
                mock.patch.object(bot_ci, 'send_create_virtualenv_fail_message'
                                  ) as send_create_virtualenv_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_install_requirements_fail_message'
                                  ) as send_install_requirements_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_run_tests_fail_message'
                                  ) as send_run_tests_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_get_coverage_fail_message'
                                  ) as send_get_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_low_coverage_fail_message'
                                  ) as send_low_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_restart_fail_message'
                                  ) as send_restart_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_new_version_message'
                                  ) as send_new_version_message_mock:

            try:
                bot_ci.release_flow()
            except SystemExit:
                pass

            self.assertIsNone(bot_ci.coverage)

            # Check methods calls
            error_mock.assert_called_once()
            call_create_virtualenv_mock.assert_called_once_with()
            call_install_requirements_mock.assert_not_called()
            call_run_tests_mock.assert_not_called()
            call_get_coverage_percentage_mock.assert_not_called()
            restart_bot_mock.assert_not_called()
            send_create_virtualenv_fail_message_mock.assert_called_once_with()
            send_install_requirements_fail_message_mock.assert_not_called()
            send_run_tests_fail_message_mock.assert_not_called()
            send_get_coverage_fail_message_mock.assert_not_called()
            send_low_coverage_fail_message_mock.assert_not_called()
            send_restart_fail_message_mock.assert_not_called()
            send_new_version_message_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_release_flow_fail_install_requirements(self, *args):
        bot_ci = BotCi(repo_path=get_random_path(), branch='master', min_coverage=100)

        with mock.patch.object(bot_ci, 'error', side_effect=SystemExit) as error_mock, \
                mock.patch.object(bot_ci, 'call_create_virtualenv', return_value=0) as call_create_virtualenv_mock, \
                mock.patch.object(bot_ci, 'call_install_requirements',
                                  return_value=1) as call_install_requirements_mock, \
                mock.patch.object(bot_ci, 'call_run_tests', return_value=0) as call_run_tests_mock, \
                mock.patch.object(bot_ci, 'call_get_coverage_percentage',
                                  return_value=0) as call_get_coverage_percentage_mock, \
                mock.patch.object(bot_ci, 'restart_bot', return_value=0) as restart_bot_mock, \
                mock.patch.object(bot_ci, 'send_create_virtualenv_fail_message'
                                  ) as send_create_virtualenv_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_install_requirements_fail_message'
                                  ) as send_install_requirements_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_run_tests_fail_message'
                                  ) as send_run_tests_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_get_coverage_fail_message'
                                  ) as send_get_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_low_coverage_fail_message'
                                  ) as send_low_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_restart_fail_message'
                                  ) as send_restart_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_new_version_message'
                                  ) as send_new_version_message_mock:

            try:
                bot_ci.release_flow()
            except SystemExit:
                pass

            self.assertIsNone(bot_ci.coverage)

            # Check methods calls
            error_mock.assert_called_once()
            call_create_virtualenv_mock.assert_called_once_with()
            call_install_requirements_mock.assert_called_once_with()
            call_run_tests_mock.assert_not_called()
            call_get_coverage_percentage_mock.assert_not_called()
            restart_bot_mock.assert_not_called()
            send_create_virtualenv_fail_message_mock.assert_not_called()
            send_install_requirements_fail_message_mock.assert_called_once_with()
            send_run_tests_fail_message_mock.assert_not_called()
            send_get_coverage_fail_message_mock.assert_not_called()
            send_low_coverage_fail_message_mock.assert_not_called()
            send_restart_fail_message_mock.assert_not_called()
            send_new_version_message_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_release_flow_fail_run_tests(self, *args):
        bot_ci = BotCi(repo_path=get_random_path(), branch='master', min_coverage=100)

        with mock.patch.object(bot_ci, 'error', side_effect=SystemExit) as error_mock, \
                mock.patch.object(bot_ci, 'call_create_virtualenv', return_value=0) as call_create_virtualenv_mock, \
                mock.patch.object(bot_ci, 'call_install_requirements',
                                  return_value=0) as call_install_requirements_mock, \
                mock.patch.object(bot_ci, 'call_run_tests', return_value=1) as call_run_tests_mock, \
                mock.patch.object(bot_ci, 'call_get_coverage_percentage',
                                  return_value=0) as call_get_coverage_percentage_mock, \
                mock.patch.object(bot_ci, 'restart_bot', return_value=0) as restart_bot_mock, \
                mock.patch.object(bot_ci, 'send_create_virtualenv_fail_message'
                                  ) as send_create_virtualenv_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_install_requirements_fail_message'
                                  ) as send_install_requirements_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_run_tests_fail_message'
                                  ) as send_run_tests_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_get_coverage_fail_message'
                                  ) as send_get_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_low_coverage_fail_message'
                                  ) as send_low_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_restart_fail_message'
                                  ) as send_restart_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_new_version_message'
                                  ) as send_new_version_message_mock:

            try:
                bot_ci.release_flow()
            except SystemExit:
                pass

            self.assertIsNone(bot_ci.coverage)

            # Check methods calls
            error_mock.assert_called_once()
            call_create_virtualenv_mock.assert_called_once_with()
            call_install_requirements_mock.assert_called_once_with()
            call_run_tests_mock.assert_called_once_with()
            call_get_coverage_percentage_mock.assert_not_called()
            restart_bot_mock.assert_not_called()
            send_create_virtualenv_fail_message_mock.assert_not_called()
            send_install_requirements_fail_message_mock.assert_not_called()
            send_run_tests_fail_message_mock.assert_called_once_with()
            send_get_coverage_fail_message_mock.assert_not_called()
            send_low_coverage_fail_message_mock.assert_not_called()
            send_restart_fail_message_mock.assert_not_called()
            send_new_version_message_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_release_flow_fail_get_coverage(self, *args):
        bot_ci = BotCi(repo_path=get_random_path(), branch='master', min_coverage=100)

        with mock.patch.object(bot_ci, 'error', side_effect=SystemExit) as error_mock, \
                mock.patch.object(bot_ci, 'call_create_virtualenv', return_value=0) as call_create_virtualenv_mock, \
                mock.patch.object(bot_ci, 'call_install_requirements',
                                  return_value=0) as call_install_requirements_mock, \
                mock.patch.object(bot_ci, 'call_run_tests', return_value=0) as call_run_tests_mock, \
                mock.patch.object(bot_ci, 'call_get_coverage_percentage',
                                  return_value=1) as call_get_coverage_percentage_mock, \
                mock.patch.object(bot_ci, 'restart_bot', return_value=0) as restart_bot_mock, \
                mock.patch.object(bot_ci, 'send_create_virtualenv_fail_message'
                                  ) as send_create_virtualenv_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_install_requirements_fail_message'
                                  ) as send_install_requirements_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_run_tests_fail_message'
                                  ) as send_run_tests_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_get_coverage_fail_message'
                                  ) as send_get_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_low_coverage_fail_message'
                                  ) as send_low_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_restart_fail_message'
                                  ) as send_restart_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_new_version_message'
                                  ) as send_new_version_message_mock:

            try:
                bot_ci.release_flow()
            except SystemExit:
                pass

            self.assertIsNone(bot_ci.coverage)

            # Check methods calls
            error_mock.assert_called_once()
            call_create_virtualenv_mock.assert_called_once_with()
            call_install_requirements_mock.assert_called_once_with()
            call_run_tests_mock.assert_called_once_with()
            call_get_coverage_percentage_mock.assert_called_once_with()
            restart_bot_mock.assert_not_called()
            send_create_virtualenv_fail_message_mock.assert_not_called()
            send_install_requirements_fail_message_mock.assert_not_called()
            send_run_tests_fail_message_mock.assert_not_called()
            send_get_coverage_fail_message_mock.assert_called_once_with()
            send_low_coverage_fail_message_mock.assert_not_called()
            send_restart_fail_message_mock.assert_not_called()
            send_new_version_message_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_release_flow_coverage_low(self, *args):
        bot_ci = BotCi(repo_path=get_random_path(), branch='master', min_coverage=100)

        def set_coverage():
            bot_ci.coverage = 99

        with mock.patch.object(bot_ci, 'error', side_effect=SystemExit) as error_mock, \
                mock.patch.object(bot_ci, 'call_create_virtualenv', return_value=0) as call_create_virtualenv_mock, \
                mock.patch.object(bot_ci, 'call_install_requirements',
                                  return_value=0) as call_install_requirements_mock, \
                mock.patch.object(bot_ci, 'call_run_tests', return_value=0) as call_run_tests_mock, \
                mock.patch.object(bot_ci, 'call_get_coverage_percentage',
                                  return_value=0, side_effect=set_coverage) as call_get_coverage_percentage_mock, \
                mock.patch.object(bot_ci, 'restart_bot', return_value=0) as restart_bot_mock, \
                mock.patch.object(bot_ci, 'send_create_virtualenv_fail_message'
                                  ) as send_create_virtualenv_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_install_requirements_fail_message'
                                  ) as send_install_requirements_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_run_tests_fail_message'
                                  ) as send_run_tests_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_get_coverage_fail_message'
                                  ) as send_get_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_low_coverage_fail_message'
                                  ) as send_low_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_restart_fail_message'
                                  ) as send_restart_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_new_version_message'
                                  ) as send_new_version_message_mock:

            try:
                bot_ci.release_flow()
            except SystemExit:
                pass

            self.assertEqual(bot_ci.coverage, 99)

            # Check methods calls
            error_mock.assert_called_once()
            call_create_virtualenv_mock.assert_called_once_with()
            call_install_requirements_mock.assert_called_once_with()
            call_run_tests_mock.assert_called_once_with()
            call_get_coverage_percentage_mock.assert_called_once_with()
            restart_bot_mock.assert_not_called()
            send_create_virtualenv_fail_message_mock.assert_not_called()
            send_install_requirements_fail_message_mock.assert_not_called()
            send_run_tests_fail_message_mock.assert_not_called()
            send_get_coverage_fail_message_mock.assert_not_called()
            send_low_coverage_fail_message_mock.assert_called_once_with()
            send_restart_fail_message_mock.assert_not_called()
            send_new_version_message_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_release_flow_fail_restart_bot(self, *args):
        bot_ci = BotCi(repo_path=get_random_path(), branch='master', min_coverage=100)

        def set_coverage():
            bot_ci.coverage = 100

        with mock.patch.object(bot_ci, 'error', side_effect=SystemExit) as error_mock, \
                mock.patch.object(bot_ci, 'call_create_virtualenv', return_value=0) as call_create_virtualenv_mock, \
                mock.patch.object(bot_ci, 'call_install_requirements',
                                  return_value=0) as call_install_requirements_mock, \
                mock.patch.object(bot_ci, 'call_run_tests', return_value=0) as call_run_tests_mock, \
                mock.patch.object(bot_ci, 'call_get_coverage_percentage',
                                  return_value=0, side_effect=set_coverage) as call_get_coverage_percentage_mock, \
                mock.patch.object(bot_ci, 'restart_bot', return_value=1) as restart_bot_mock, \
                mock.patch.object(bot_ci, 'send_create_virtualenv_fail_message'
                                  ) as send_create_virtualenv_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_install_requirements_fail_message'
                                  ) as send_install_requirements_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_run_tests_fail_message'
                                  ) as send_run_tests_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_get_coverage_fail_message'
                                  ) as send_get_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_low_coverage_fail_message'
                                  ) as send_low_coverage_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_restart_fail_message'
                                  ) as send_restart_fail_message_mock, \
                mock.patch.object(bot_ci, 'send_new_version_message'
                                  ) as send_new_version_message_mock:

            try:
                bot_ci.release_flow()
            except SystemExit:
                pass

            self.assertEqual(bot_ci.coverage, 100)

            # Check methods calls
            error_mock.assert_called_once()
            call_create_virtualenv_mock.assert_called_once_with()
            call_install_requirements_mock.assert_called_once_with()
            call_run_tests_mock.assert_called_once_with()
            call_get_coverage_percentage_mock.assert_called_once_with()
            restart_bot_mock.assert_called_once_with()
            send_create_virtualenv_fail_message_mock.assert_not_called()
            send_install_requirements_fail_message_mock.assert_not_called()
            send_run_tests_fail_message_mock.assert_not_called()
            send_get_coverage_fail_message_mock.assert_not_called()
            send_low_coverage_fail_message_mock.assert_not_called()
            send_restart_fail_message_mock.assert_called_once_with()
            send_new_version_message_mock.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_run(self, *args):
        def error(msg):
            self.fail('error() method called: %s' % msg)

        bot_ci = BotCi(repo_path=get_random_path(), branch='master')

        c1 = FakeCommit()
        c2 = FakeCommit([c1])
        c3 = FakeCommit([c2])
        c4 = FakeCommit([c2])

        tagv1 = FakeTagRef(path='v1', object=c1)
        tagv2 = FakeTagRef(path='v2', object=c2)

        master = FakeRef(path='origin/master', object=c3)
        dev = FakeRef(path='origin/dev', object=c4)

        repo = mock.Mock()
        repo.git.describe.return_value = 'v1.0'
        custom_environment = mock.MagicMock()
        repo.git.custom_environment.return_value = custom_environment
        refs = mock.PropertyMock(return_value=[dev, master])
        type(repo.remotes.origin).refs = refs
        tags = mock.PropertyMock(return_value=[tagv1, tagv2])
        type(repo).tags = tags
        head_commit = mock.PropertyMock(return_value=c1)
        type(repo.head).commit = head_commit

        with mock.patch.object(bot_ci, 'clone_repo') as clone_repo_mock, \
                mock.patch.object(bot_ci, 'error', side_effect=error), \
                mock.patch.object(bot_ci, 'get_last_tag', return_value=tagv2) as get_last_tag_mock, \
                mock.patch.object(bot_ci, 'release_flow') as release_flow_mock, \
                mock.patch.object(Repo, 'init', return_value=repo) as init_mock:

            try:
                bot_ci.run()
            except SystemExit:
                pass

            self.assertEqual(bot_ci.remote_commit, master)
            self.assertEqual(bot_ci.last_tag, tagv2)
            self.assertEqual(bot_ci.version, 'v2')
            self.assertEqual(bot_ci.author, c1.author.name)

            # Check methods calls
            clone_repo_mock.assert_called_once_with()
            init_mock.assert_called_once_with(bot_ci.repo_path)
            repo.git.describe.assert_called_once_with('--always')
            repo.git.custom_environment.assert_called_once_with(GIT_SSH_COMMAND=bot_ci.ssh_cmd)
            repo.remotes.origin.fetch.assert_called_once_with(['--tags', '-f'])
            refs.assert_called_once_with()
            tags.assert_called_once_with()
            get_last_tag_mock.assert_called_once_with(c3)
            repo.head.reset.assert_called_once_with(tagv2, index=True, working_tree=True)
            release_flow_mock.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_run_missing_branch(self, *args):
        bot_ci = BotCi(repo_path=get_random_path(), branch='master')

        with mock.patch.object(bot_ci, 'clone_repo') as clone_repo_mock, \
                mock.patch.object(bot_ci, 'error', side_effect=SystemExit) as error_mock, \
                mock.patch.object(Repo, 'init') as init_mock:
            repo = mock.Mock()
            repo.git.describe.return_value = 'v1.0'
            custom_environment = mock.MagicMock()
            repo.git.custom_environment.return_value = custom_environment
            refs = mock.PropertyMock(return_value=[])
            type(repo.remotes.origin).refs = refs
            init_mock.return_value = repo

            try:
                bot_ci.run()
            except SystemExit:
                pass

            self.assertIsNone(bot_ci.remote_commit)

            # Check that there are not error
            error_mock.assert_called_once_with('Missing origin/master')

            # Check methods calls
            clone_repo_mock.assert_called_once_with()
            init_mock.assert_called_once_with(bot_ci.repo_path)
            repo.git.describe.assert_called_once_with('--always')
            repo.git.custom_environment.assert_called_once_with(GIT_SSH_COMMAND=bot_ci.ssh_cmd)
            repo.remotes.origin.fetch.assert_called_once_with(['--tags', '-f'])
            refs.assert_called_once_with()

    @mock.patch.object(BotCi, 'check')
    def test_run_no_tags(self, *args):
        def error(msg):
            self.fail('error() method called: %s' % msg)

        bot_ci = BotCi(repo_path=get_random_path(), branch='master')

        c1 = FakeCommit()
        c2 = FakeCommit([c1])
        c3 = FakeCommit([c1])

        tag = FakeTagRef(path='v1', object=c3)

        dev = FakeRef(path='origin/dev', object=c3)
        master = FakeRef(path='origin/master', object=c2)

        repo = mock.Mock()
        repo.git.describe.return_value = 'v1.0'
        custom_environment = mock.MagicMock()
        repo.git.custom_environment.return_value = custom_environment
        refs = mock.PropertyMock(return_value=[dev, master])
        type(repo.remotes.origin).refs = refs
        tags = mock.PropertyMock(return_value=[tag])
        type(repo).tags = tags

        with mock.patch.object(bot_ci, 'clone_repo') as clone_repo_mock, \
                mock.patch.object(bot_ci, 'error', side_effect=error), \
                mock.patch.object(bot_ci, 'get_last_tag', return_value=None) as get_last_tag_mock, \
                mock.patch.object(Repo, 'init', return_value=repo) as init_mock:

            try:
                bot_ci.run()
            except SystemExit:
                pass

            self.assertEqual(bot_ci.remote_commit, master)
            self.assertIsNone(bot_ci.last_tag)
            self.assertIsNone(bot_ci.version)
            self.assertIsNone(bot_ci.author)

            # Check methods calls
            clone_repo_mock.assert_called_once_with()
            init_mock.assert_called_once_with(bot_ci.repo_path)
            repo.git.describe.assert_called_once_with('--always')
            repo.git.custom_environment.assert_called_once_with(GIT_SSH_COMMAND=bot_ci.ssh_cmd)
            repo.remotes.origin.fetch.assert_called_once_with(['--tags', '-f'])
            refs.assert_called_once_with()
            tags.assert_called_once_with()
            get_last_tag_mock.assert_called_once_with(c2)
            repo.head.assert_not_called()

    @mock.patch.object(BotCi, 'check')
    def test_run_up_to_date(self, *args):
        def error(msg):
            self.fail('error() method called: %s' % msg)

        bot_ci = BotCi(repo_path=get_random_path(), branch='master')

        c1 = FakeCommit()
        c2 = FakeCommit()
        c3 = FakeCommit([c2])
        c4 = FakeCommit([c2])

        tagv1 = FakeTagRef(path='v1', object=c1)
        tagv2 = FakeTagRef(path='v2', object=c2)

        master = FakeRef(path='origin/master', object=c3)
        dev = FakeRef(path='origin/dev', object=c4)

        repo = mock.Mock()
        repo.git.describe.return_value = 'v1.0'
        custom_environment = mock.MagicMock()
        repo.git.custom_environment.return_value = custom_environment
        refs = mock.PropertyMock(return_value=[dev, master])
        type(repo.remotes.origin).refs = refs
        tags = mock.PropertyMock(return_value=[tagv1, tagv2])
        type(repo).tags = tags
        head_commit = mock.PropertyMock(return_value=c2)
        type(repo.head).commit = head_commit
        repo.head.reset.side_effect = SystemExit

        with mock.patch.object(bot_ci, 'clone_repo') as clone_repo_mock, \
                mock.patch.object(bot_ci, 'error', side_effect=error), \
                mock.patch.object(bot_ci, 'get_last_tag', return_value=tagv2) as get_last_tag_mock, \
                mock.patch.object(Repo, 'init', return_value=repo) as init_mock:

            try:
                bot_ci.run()
            except SystemExit:
                pass

            self.assertEqual(bot_ci.last_tag, tagv2)
            self.assertEqual(bot_ci.version, 'v2')
            self.assertEqual(bot_ci.author, c1.author.name)

            # Check methods calls
            clone_repo_mock.assert_called_once_with()
            init_mock.assert_called_once_with(bot_ci.repo_path)
            repo.git.describe.assert_called_once_with('--always')
            repo.git.custom_environment.assert_called_once_with(GIT_SSH_COMMAND=bot_ci.ssh_cmd)
            repo.remotes.origin.fetch.assert_called_once_with(['--tags', '-f'])
            refs.assert_called_once_with()
            tags.assert_called_once_with()
            get_last_tag_mock.assert_called_once_with(c3)
            repo.head.reset.assert_not_called()

    def test_main(self):
        with mock.patch('bot_ci.load_dotenv') as load_dotenv_mock, \
                mock.patch('logging.basicConfig') as basicConfig_mock, \
                mock.patch.object(sys, 'argv', ['capitalismo_bot.py']), \
                mock.patch.object(BotCi, 'check') as check_mock, \
                mock.patch.object(BotCi, 'run') as run_mock:
            main()

            basicConfig_mock.assert_called_once_with(
                filename=None,
                format='%(asctime)s - %(levelname)s - %(message)s',
                level=logging.INFO,
            )

            load_dotenv_mock.assert_called_once()
            load_dotenv_mock.assert_called_once()
            check_mock.assert_called_once_with()
            run_mock.assert_called_once_with()
