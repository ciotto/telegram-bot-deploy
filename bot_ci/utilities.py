import os


def get_parse_array(parser=None):
    def parse_array(value):
        return [parser(s.strip()) if parser else s.strip() for s in value.split(',')]
    return parse_array


def getenv(key, default=None, parser=None):
    value = os.getenv(key, default)
    if value and parser:
        return parser(value)
    return value


def send(bot, chat_id, msg):
    bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
