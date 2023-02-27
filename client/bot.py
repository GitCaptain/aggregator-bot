import logging
from typing import Coroutine
import telethon
from file_processor import FileProcessor
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import (ChannelsTooMuchError,
                             ChannelIdInvalidError,
                             ChannelPrivateError,
                             InviteRequestSentError)

class Bot:

    def __init__(self,
                 client: telethon.TelegramClient,
                 main_channel: str,
                 file_processor: FileProcessor) -> None:
        self.client = client
        self.file_processor = file_processor
        self.logger = logging.getLogger('Main.bot')

    async def start(self) -> None:
        self.logger.info('bot started')
        self.logger.debug('signed in as: %s', (await self.client.get_me()).stringify())
        await self._mainloop()

    async def _mainloop(self) -> None:
        await self._subscribe_channels()
        # await time.sleep(10)

    async def _enumerate_channels(self) -> list[Coroutine]:
        channels_username = self.file_processor.channel_generator()
        channel_entities = []
        for channel in channels_username:
            try:
                ent = self.client.get_input_entity(channel)
            except ValueError:
                self.logger.error("Can't find input_entity for channel: %s", channel)
            channel_entities.append(self.client.get_entity(await ent))
        return channel_entities

    async def _subscribe_channels(self) -> None:
        channel_entities = await self._enumerate_channels()
        channels_info = []
        join_requests = []
        err_msg = 'Unable to join channel: %s, reason: %s'

        for ent in channel_entities:
            channel = await ent
            channels_info.append(f'{channel.title} ({channel.username})')
            join_requests.append(self.client(JoinChannelRequest(channel)))

        for request, info in zip(join_requests, channels_info):
            try:
                result = await request
            except ChannelsTooMuchError:
                self.logger.error(
                    err_msg, info, 'You have joined too many channels/supergroups.')
            except ChannelIdInvalidError:
                self.logger.error(
                    err_msg, info, 'Invalid channel object. '
                    'Make sure to pass the right types, for instance making sure that the request '
                    'is designed for channels or otherwise look for a different one more suited.')
            except ChannelPrivateError:
                self.logger.error(
                    err_msg, info,
                    'The channel specified is private and you lack permission to access it. '
                    'Another reason may be that you were banned from it.'
                )
            except InviteRequestSentError:
                # Not sure what this error means, taken from docs
                # https://tl.telethon.dev/methods/channels/join_channel.html
                self.logger.error('You have successfully requested to join this chat or channel.')
            self.logger.info('Join channel request result: %s', result.stringify())
