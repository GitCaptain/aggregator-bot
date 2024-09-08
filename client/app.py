import logging
import os
import sys

from bot import Bot
from database.database import Database
from file_processor import FileProcessor
from telethon import TelegramClient


class App:

    def __init__(self, api_id: str, api_hash: str, work_dir: str) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.logger = logging.getLogger('Main.app')
        self.working_dir = work_dir
        os.makedirs(self.working_dir, exist_ok=True)

    def start(self, session_name: str, main_channel: str, channel_file: str) -> None:
        self.logger.info('App started')
        session = os.path.join(self.working_dir, session_name)
        with TelegramClient(session, int(self.api_id), self.api_hash) as client:
            while True:
                try:
                    client.loop.run_until_complete(
                        Bot(self,
                            client,
                            Database(self.database_path),
                            FileProcessor(channel_file))
                                .start(main_channel))
                except Exception as e:
                    self.logger.error('Unhandled exception: %s', e)

    @property
    def database_path(self) -> str:
        return os.path.join(self.working_dir, 'client.db')

    @property
    def working_dir(self) -> str:
        return self._working_dir

    @working_dir.setter
    def working_dir(self, dir) -> None:
        self._working_dir = dir
