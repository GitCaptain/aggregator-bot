import logging
from telethon import TelegramClient
from bot import Bot
from file_processor import FileProcessor
class App:

    def __init__(self,
                 api_id: str,
                 api_hash: str,
                 main_channel: str,
                 channel_file: str,
                 session_name: str) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.logger = logging.getLogger('Main.app')
        self.main_channel = main_channel
        self.file_processor = FileProcessor(channel_file)

    def start(self) -> None:
        self.logger.info('App started')
        with TelegramClient(self.session_name, self.api_id, self.api_hash) as client:
            client.loop.run_until_complete(Bot(client, self.main_channel, self.file_processor)
                                            .start())
