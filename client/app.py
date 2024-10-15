import logging
import os
import sys

from bot import Bot
from file_processor import FileProcessor
from telethon import TelegramClient, events


class App:

    def __init__(self, api_id: str, api_hash: str, work_dir: str) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.logger = logging.getLogger('Main.app')
        self.working_dir = work_dir
        os.makedirs(self.working_dir, exist_ok=True)

    def start(self, session_name: str, main_channel: str, channel_file: str, memes_folder: str) -> None:
        self.logger.info('App started')
        session = os.path.join(self.working_dir, session_name)
        with TelegramClient(session, int(self.api_id), self.api_hash) as client:
            bot = Bot(self, client, FileProcessor(channel_file), memes_folder)
            bot.register_handlers()
            while True: # never give up!
                try:
                    client.loop.run_until_complete(bot.start(main_channel))
                except Exception as e:
                    self.logger.error('Unhandled exception: %s', e)

    @property
    def working_dir(self) -> str:
        return self._working_dir

    @working_dir.setter
    def working_dir(self, dir) -> None:
        self._working_dir = dir
