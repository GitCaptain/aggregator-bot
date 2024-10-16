"""File related utilities"""

import logging
from typing import Generator


class FileProcessor:
    """Process file with channel info"""

    # pylint: disable=too-few-public-methods
    def __init__(self, file: str) -> None:
        self.file = file
        self.logger = logging.getLogger('Main.file_processor')

    def channel_generator(self) -> Generator[str, None, None]:
        """Parse channel file, yields channel usernames line by line"""
        try:
            with open(self.file, encoding='utf-8') as channels:
                for channel in channels:
                    channel = channel.strip()
                    self.logger.info('channel parsed: %s', channel)
                    if channel.startswith('#'):
                        self.logger.debug('skip current channel')
                        continue
                    yield channel
        except FileNotFoundError:
            # we do not want to shutdown bot if nothing found
            # file may be created on next call to this function or we already read what we need.
            self.logger.error(
                'File %s not found, create file or check path', self.file
            )
