"""Main bot functions"""

import asyncio
import logging
from typing import Any, Coroutine

import app
import telethon
from file_processor import FileProcessor
from telethon import events
from telethon.errors import (
    ChannelIdInvalidError,
    ChannelPrivateError,
    ChannelsTooMuchError,
    InviteRequestSentError,
)
from telethon.events.common import EventBuilder
from telethon.functions import messages
from telethon.tl import types
from telethon.tl.functions.channels import JoinChannelRequest


class Bot:
    """The bot which is downloading content from channels and repost it"""

    def __init__(
        self,
        owner: 'app.App',
        client: telethon.TelegramClient,
        file_processor: FileProcessor,
        memes_folder: str,
    ) -> None:
        self.client = client
        self.file_processor = file_processor
        self.owner = owner
        self.logger = logging.getLogger('Main.bot')
        self.main_channel = None
        self.channels = None
        self.memes_folder = memes_folder
        # pylint: disable=invalid-name
        self.me = None

    async def onNewMessage(self, event: events.NewMessage):
        self.logger.info(
            'Got new message %s\ntype: %s\ndata: %s',
            event,
            type(event),
            event.stringify(),
        )

    async def onAnyEvent(self, event: EventBuilder):
        self.logger.debug(
            'Got new event %s\ntype: %s\ndata: %s',
            event,
            type(event),
            event.stringify(),
        )

    def register_handlers(self):
        self.client.add_event_handler(
            self.onNewMessage,
            events.NewMessage(
                incoming=True, forwards=False, from_users=self.channels
            ),
        )
        self.client.add_event_handler(self.onAnyEvent, events.Album())
        self.client.add_event_handler(self.onAnyEvent, events.CallbackQuery())
        self.client.add_event_handler(self.onAnyEvent, events.ChatAction())
        self.client.add_event_handler(self.onAnyEvent, events.MessageDeleted())
        self.client.add_event_handler(self.onAnyEvent, events.InlineQuery())
        self.client.add_event_handler(self.onAnyEvent, events.MessageEdited())
        self.client.add_event_handler(self.onAnyEvent, events.MessageRead())
        self.client.add_event_handler(self.onAnyEvent, events.Raw())
        self.client.add_event_handler(self.onAnyEvent, events.UserUpdate())

    async def start(self, main_channel: str) -> None:
        """Bot entrypoint"""
        self.logger.info('bot started')
        self.logger.debug(
            'signed in as: %s', (await self.client.get_me()).stringify()
        )
        main_channel_input_entt = await self.client.get_input_entity(
            main_channel
        )
        self.main_channel = await self.client.get_entity(
            main_channel_input_entt
        )
        await self._main()

    async def get_meme_folder_id(self) -> int:
        folders: types.messages.DialogFilters = await self.client(
            messages.GetDialogFiltersRequest())  # type: ignore
        self.logger.debug(
            'Enumerated folders: %s\ntype: %s',
            folders.stringify(),
            type(folders),
        )
        for e in folders.filters:
            self.logger.debug('folder: %s\ntype: %s', e.stringify(), type(e))
        try:
            meme_folder_id = next(  # we only check one for now
                filter(
                    lambda x: isinstance(x, types.DialogFilter)
                    and x.title == self.memes_folder,
                    folders.filters,
                )
            ).id
        except StopIteration:
            self.logger.warning(
                'Folder with name %s not found!', self.memes_folder
            )
            return -1
        self.logger.debug('Meme folder id: %s', meme_folder_id)
        return meme_folder_id

    async def get_subscribed_channels(self) -> set[str]:
        return set()

    async def _main(self) -> None:
        """main program loop: subscribe, restore info, get content,
        send content, save content"""

        channels, subscribed, meme_folder_id = await asyncio.gather(
            self._enumerate_channels(),
            self.get_subscribed_channels(),
            self.get_meme_folder_id(),
        )
        usernames = set(channel.username for channel in channels)
        self.channels = usernames
        await self._subscribe_channels(channels, subscribed, meme_folder_id)
        await asyncio.Future()
        # messages = []
        # for ch_info in channels:
        #     messages.extend(await self._get_messages_since_id(ch_info.entt,
        #                                                         ch_info.latest_saved_msg_id))
        # await self._post_messages(messages, db_session)
        # self.save_info(db_session, new_channels, messages)

    # async def _get_messages_since_id(self, channel: TypeChat, msg_id: int = 0) \
    #     -> list[list[MessageUpd]]:
    #     """Get messages from channel starting from msg_id"""
    #     messages = []
    #     # fetch 10 latest message (max in one group)
    #     limit = 10
    #     last_grouped_id = None
    #     msg: Message
    #     async for msg in self.client.iter_messages(channel, limit=limit, min_id=msg_id):
    #         logging.debug('get msg from chat %s, msg:', channel.title)
    #         logging.debug(msg.stringify())
    #         if not msg.video and not msg.photo and not msg.gif:
    #             logging.debug('Msg with id %s: is not photo, video or gif', msg.id)
    #             continue
    #         if msg.grouped_id is None or msg.grouped_id != last_grouped_id:
    #             last_grouped_id = msg.grouped_id
    #             messages.append([])
    #         try:
    #             urls = msg.get_entities_text(MessageEntityTextUrl)
    #             media_b: bytes = await msg.download_media(file=bytes)
    #             m_upd = MessageUpd(msg.id, msg.grouped_id, channel.id, msg.text, msg.media, media_b,
    #                                bool(urls))
    #             messages[-1].append(m_upd)
    #         except ValueError as v:
    #             self.logger.error('Can't create MessageUpd, err: %s', v)
    #     return messages

    # def _is_text_ok(self, msg_text: str, url: bool):
    #     """Do my best to filter out messages"""
    #     if url:
    #         # probably some advertisement link
    #         return False
    #     if len(msg_text) > 50:
    #         # too long for meme
    #         return False
    #     if '#' in msg_text:
    #         # probably some #adv tag
    #         return False
    #     return True

    # async def _post_messages(self, messages: list[list[MessageUpd]], db_session: Session) -> None:
    #     """Post messages to main_channel"""
    #     posted = self._get_posted(map(lambda msg: msg.sha256,
    #                                   itertools.chain.from_iterable(messages)),
    #                               db_session)
    #     # Post in reverse order, since we add latest messages to the end of list
    #     for msg_group in messages[::-1]:
    #         # do not post messages if full group posted already
    #         # if only some messages from the group exist - it may be new meme
    #         if set(map(lambda msg: msg.sha256, msg_group)).issubset(posted):
    #             continue
    #         text = ''
    #         files = []
    #         url = False
    #         for msg in msg_group[::-1]:
    #             text = msg.text or text
    #             url = msg.url or url
    #             files.append(msg.media_ref)
    #         if not self._is_text_ok(text, url):
    #             # do not post this message, but save it to db to filter it out on the previous step.
    #             continue
    #         try:
    #             await self.client.send_file(self.main_channel, files, caption=text)
    #         except (telethon.errors.rpcbaseerrors.BadRequestError, TypeError) as err:
    #             self.logger.error('Can't send media: %s', err)
    #         except Exception as err: # something wrong, but I don't want to die here
    #             self.logger.error('Unexpected exception durung message posting: %s', err)

    async def _enumerate_channels(self) -> list[types.Channel]:
        """Get already subscribed channels"""
        channels_username = self.file_processor.channel_generator()
        channels: list[types.Channel] = []
        for channel_uname in channels_username:
            # TODO: how to manage closed channels?
            # i.e. what to use instead of username? hash?
            # tme_prefix='https://t.me/'
            # joinchat='joinchat/'
            # if channel_uname.startswith(tme_prefix):
            #     link = channel_uname\
            #             .replace(tme_prefix, '').replace(joinchat, '', 1).replace('+', '', 1)
            #     self.logger.debug('trying to joing via link: %s', link)
            #     try:
            #         upd: Updates = await self.client(ImportChatInviteRequest(link))
            #         self.logger.debug('get upd from private channel: %s', upd.stringify())
            #         # channels.append(upd) ??
            #     except (telethon.errors.rpcerrorlist.InviteHashExpiredError,
            #             telethon.errors.rpcerrorlist.InviteHashEmptyError,
            #             telethon.errors.rpcerrorlist.InviteHashInvalidError,
            #             telethon.errors.rpcerrorlist.UserAlreadyParticipantError,
            #             telethon.errors.rpcerrorlist.InviteRequestSentError,) as err:
            #         self.logger.error('Error while trying to join private channel: %s', err)
            try:
                ent = await self.client.get_input_entity(channel_uname)
                channel = await self.client.get_entity(ent)
                if not isinstance(channel, types.Channel):
                    self.logger.warning(
                        "Expected %s to be a Channel, but it's type is: %s",
                        channel_uname,
                        type(channel),
                    )
                else:
                    channels.append(channel)
            except (ValueError, TypeError) as e:
                self.logger.warning(
                    "Can't find input_entity for channel: %s\nGot err: %s",
                    channel_uname,
                    e,
                )
        self.logger.info(
            'Channels enumerated: %s',
            list(channel.username for channel in channels),
        )
        return channels

    async def _subscribe_channels(
        self,
        channels: list[types.Channel],
        subscribed: set[str],
        meme_folder_id: int,
    ) -> None:
        """Subscribe to channels"""
        err_msg = 'Unable to join channel: %s, reason: %s'
        # TODO: Mute and archive all chats
        futures: list[Coroutine[Any, Any, types.Updates]] = []
        for channel in channels:
            info = f'{channel.title} (@{channel.username})'
            if channel.username in subscribed:
                futures.append(self.client.edit_folder(channel, 1))
                self.logger.debug('skip channel %s, already subscribed', info)
                continue
            try:
                if channel.access_hash is None:
                    self.logger.warning(
                        'access_hash field is expected, but not set for: %s',
                        info,
                    )
                    continue
                ic = types.InputChannel(channel.id, channel.access_hash)
                result = await self.client(JoinChannelRequest(ic))
                # WTF IS RESULT??
                self.logger.info(
                    'Joining channel result:\n\tres: %s\n\ttype: %s',
                    result,
                    type(result),
                )
                # self.logger.info('Join channel request result: %s', result.stringify())
            except ChannelsTooMuchError:
                self.logger.error(
                    err_msg,
                    info,
                    'You have joined too many channels/supergroups.',
                )
            except ChannelIdInvalidError:
                self.logger.error(
                    err_msg,
                    info,
                    'Invalid channel object. '
                    'Make sure to pass the right types, for instance making '
                    'sure that the request is designed for channels or '
                    'otherwise look for a different one more suited.',
                )
            except ChannelPrivateError:
                self.logger.error(
                    err_msg,
                    info,
                    'The channel specified is private and you lack permission '
                    'to access it. Another reason may be that you were banned '
                    'from it.',
                )
            except InviteRequestSentError:
                # Not sure what this error means, taken from docs
                # https://tl.telethon.dev/methods/channels/join_channel.html
                self.logger.error(
                    'You have successfully requested to join this chat or '
                    'channel.'
                )
