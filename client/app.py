import logging
from telethon import TelegramClient
from bot import Bot

class App:

    def __init__(self, api_id: str, api_hash: str, channel_file: str, session_name: str) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.channel_file = channel_file
        self.session_name = session_name
        self.logger = logging.getLogger('Main.app')

    def start(self) -> None:
        self.logger.info('App started')
        with TelegramClient(self.session_name, self.api_id, self.api_hash) as client:
            client.loop.run_until_complete(Bot(client).start())
