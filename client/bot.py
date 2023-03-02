import logging
import os
from datetime import datetime, timedelta

import app
import telethon
from file_processor import FileProcessor
from telethon.errors import (ChannelIdInvalidError, ChannelPrivateError,
                             ChannelsTooMuchError, InviteRequestSentError)
from telethon.tl.custom.message import Message
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import (InputMessagesFilterChatPhotos,
                               InputMessagesFilterGif,
                               InputMessagesFilterPhotoVideo, TypeChat)


class Bot:

    def __init__(self,
                 owner: 'app.App',
                 client: telethon.TelegramClient,
                 file_processor: FileProcessor) -> None:
        self.client = client
        self.file_processor = file_processor
        self.owner = owner
        self.logger = logging.getLogger('Main.bot')
        self.me = None
        self.main_channel = None

    async def start(self, main_channel: str) -> None:
        self.logger.info('bot started')
        self.logger.debug('signed in as: %s', (await self.client.get_me()).stringify())
        main_channel_input_entt = self.client.get_input_entity(main_channel)
        self.main_channel = await self.client.get_entity(await main_channel_input_entt)
        await self._mainloop()

    async def _mainloop(self) -> None:
        channels = await self._enumerate_channels()
        await self._subscribe_channels(channels)
        # future_messages = [self._get_messages_since(datetime=datetime.today() - timedelta(1), channel=channel) for channel in channels]
        # for fut in future_messages:
        #     await fut
        await self._post_messages()
        # await time.sleep(10)

    async def _get_messages_since(self, datetime: datetime, channel: TypeChat):
        msg_filter = [InputMessagesFilterPhotoVideo, InputMessagesFilterGif, InputMessagesFilterChatPhotos]
        msg: Message
        async for msg in self.client.iter_messages(channel, limit=1, offset_date=datetime): # filter=msg_filter):
            logging.debug('get msg from chat %s, msg:', channel.title)
            logging.debug(msg.stringify())
            if not msg.file:
                logging.warning('No media in msg with id %s, downloaded from channel: %s', msg.id, channel.title)
                continue
            file_name = f'{channel.title.replace("/","_")}-{msg.file.title}-{msg.id}.{msg.file.ext}'
            file_path = os.path.join(self.owner.download_dir, file_name)
            await msg.download_media(file=file_path)

    async def _post_messages(self):
        for file_name in os.listdir(self.owner.download_dir):
            print(file_name)
            with open(os.path.join(self.owner.download_dir, file_name), 'rb') as f:
                await self.client.send_file(self.main_channel, f)

    async def _enumerate_channels(self) -> list[TypeChat]:
        channels_username = self.file_processor.channel_generator()
        channels = []
        for channel_uname in channels_username:
            try:
                ent = self.client.get_input_entity(channel_uname)
            except ValueError:
                self.logger.error("Can't find input_entity for channel: %s", channel_uname)
            channel_future = self.client.get_entity(await ent)
            channels.append(await channel_future)
        return channels

    async def _subscribe_channels(self, channels: list[TypeChat]) -> None:
        channels_info = []
        join_requests = []
        err_msg = 'Unable to join channel: %s, reason: %s'

        for channel in channels:
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
