import logging
import os

from bot import Bot
from file_processor import FileProcessor
from telethon import TelegramClient


class App:

    def __init__(self, api_id: str, api_hash: str, working_dir: str) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.logger = logging.getLogger('Main.app')
        self.working_dir = working_dir

    def start(self, session_name: str, main_channel: str, channel_file: str) -> None:
        self.logger.info('App started')
        session = os.path.join(self.working_dir, session_name)
        with TelegramClient(session, self.api_id, self.api_hash) as client:
            client.loop.run_until_complete(Bot(self, client, FileProcessor(channel_file))
                                            .start(main_channel))

    @property
    def download_dir(self) -> str:
        dir = os.path.join(self.working_dir, 'downloads')
        os.makedirs(dir, exist_ok=True)
        return dir
