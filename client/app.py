import logging
import os

from bot import Bot
from exceptions import ConfigurationException
from file_processor import FileProcessor
from telethon import TelegramClient


class App:

    def __init__(self, api_id: str, api_hash: str, work_dir: str) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.logger = logging.getLogger("Main.app")
        self.working_dir = work_dir
        os.makedirs(self.working_dir, exist_ok=True)

    def start(
        self,
        session_name: str,
        main_channel: str,
        sub_channel: str,
        channel_file: str,
        memes_folder: str,
        posts_limit: int,
        delay_minutes: int,
    ) -> None:
        self.logger.info("App started")
        session = os.path.join(self.working_dir, session_name)
        with TelegramClient(session, int(self.api_id), self.api_hash) as client:
            bot = Bot(
                self,
                client,
                FileProcessor(channel_file),
                memes_folder,
                posts_limit,
                delay_minutes,
            )
            stop = False
            while not stop:  # almost never give up!
                try:
                    client.loop.run_until_complete(
                        bot.start(main_channel, sub_channel)
                    )
                except ConfigurationException as e:
                    stop = True
                    self.logger.fatal(
                        "Something problem with bot parameters, "
                        "no reason to try again:\n%s",
                        e,
                    )
                except Exception as e:
                    self.logger.error("Unhandled exception: %s", e)

    @property
    def working_dir(self) -> str:
        return self._working_dir

    @working_dir.setter
    def working_dir(self, dir) -> None:
        self._working_dir = dir
