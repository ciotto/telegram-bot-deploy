import os
import sys
import unittest

import telegram

from bot_ci.utilities import get_parse_array, send, getenv

if sys.version_info[0] < 3:
    import mock
else:
    from unittest import mock


class TestUtilities(unittest.TestCase):
    if sys.version_info[0] < 3:
        def assertCountEqual(self, *args, **kwargs):
            self.assertItemsEqual(*args, **kwargs)

    def setUp(self):
        with mock.patch.object(telegram.Bot, '_validate_token') as _validate_token_mock:
            self.bot = telegram.Bot('token')

    def test_get_parse_array(self):
        # Check w/o parser
        parser = get_parse_array()
        self.assertIsNotNone(parser)
        self.assertCountEqual(parser('asd, lol,    qwe,bau'), ['asd', 'lol', 'qwe', 'bau'])

    def test_get_parse_array_int(self):
        # Check w/ int parser
        parser = get_parse_array(int)
        self.assertIsNotNone(parser)
        self.assertCountEqual(parser('1, 2,    3,4'), [1, 2, 3, 4])

    def test_getenv(self):
        os.environ['kebab'] = 'secret'
        self.assertEqual(getenv('kebab'), 'secret')

    def test_getenv_int(self):
        os.environ['kebab'] = '123'
        self.assertEqual(getenv('kebab', default=123, parser=int), 123)
        self.assertEqual(getenv('falafel', default=123, parser=int), 123)

    def test_getenv_none(self):
        self.assertIsNone(getenv('asd'))

    def test_send(self):
        with mock.patch.object(telegram.Bot, 'send_message') as send_message_mock:
            send(self.bot, 123, 'asd')

            # Check send_message calls
            send_message_mock.assert_called_once_with(chat_id=123, text='asd', parse_mode='Markdown')
