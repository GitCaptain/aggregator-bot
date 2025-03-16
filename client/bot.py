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
from telethon.functions import messages
from telethon.tl import TLObject, custom, types
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
        # TODO: populate dinamically?
        self.filters = ['@yababapomogite']

    def check_message_intresting(self, message: custom.Message) -> bool:
        media = message.media
        if media is None:
            self.logger.info('Skip message: No media')
            return False
        if not isinstance(media, (
                        types.MessageMediaPhoto, types.MessageMediaDocument)):
            self.logger.info('Skip message: media type "%s" is not intresting',
                                type(media))
            return False
        if isinstance(media, types.MessageMediaDocument) and \
            (media.round or media.voice):
            self.logger.info('Media is voice or round - advertisement probably')
            return False
        urls = message.get_entities_text(types.MessageEntityTextUrl)
        text = message.text or ''
        if not self._is_advertising_probably(text, bool(urls)):
            self.logger.info('Skip message, maybe advertisement:\n"%s"\n', text)
            return False

        return True

    def apply_text_filters(self, message: custom.Message) -> None:
        if message.text:
            newtext = '\n'.join(
                filter(lambda s: not any(s.startswith(x) for x in self.filters),
                                 message.text.splitlines()))
            if newtext != message.text:
                self.logger.debug('message:\n"%s"\nfiltered to be:\n"%s"\n',
                                 message.text, newtext)
            message.text = newtext

    async def onNewMessage(self, event: events.NewMessage.Event) -> None:
        self.logger.info(
            'Got new message %s\ntype: %s',
            event.stringify(),
            type(event),
        )
        msg: custom.Message = event.message
        if msg.grouped_id:
            self.logger.info('This is a group of media, i.e. Album, '
                             'this should be processed separately')
            return
        if not self.check_message_intresting(msg):
            return
        self.apply_text_filters(msg)
        await self._post_messages([msg])

    async def onAlbum(self, event: events.Album.Event) -> None:
        self.logger.info(
            'Got new Album %s\ntype: %s',
            event.stringify(),
            type(event),
        )
        if any(filter(
                lambda x: not self.check_message_intresting(x), # type: ignore
                event.messages)):
            # for now we check that every message is ok,
            # to better avoid advertising.
            # Probably there should be another way.
            return
        for msg in event.messages:
            self.apply_text_filters(msg)
        await self._post_messages(event.messages, True)

    async def onAnyEvent(self, event: TLObject) -> None:
        self.logger.debug(
            'Got new event %s\ntype: %s\n',
            event.stringify(),
            type(event)
        )

    def register_handlers(self):
        self.client.add_event_handler(
            self.onNewMessage,
            events.NewMessage(
                incoming=True, forwards=False, chats=self.channels
            ),
        )
        self.client.add_event_handler(self.onAlbum, events.Album(
            chats=self.channels
        ))

        # TODO: do we want to check forwarded messages ?
        self.client.add_event_handler(self.onAnyEvent, events.UserUpdate())

        self.client.add_event_handler(self.onAnyEvent, events.CallbackQuery())
        self.client.add_event_handler(self.onAnyEvent, events.ChatAction())
        self.client.add_event_handler(self.onAnyEvent, events.MessageDeleted())
        self.client.add_event_handler(self.onAnyEvent, events.InlineQuery())
        self.client.add_event_handler(self.onAnyEvent, events.MessageEdited())
        self.client.add_event_handler(self.onAnyEvent, events.MessageRead())
        self.client.add_event_handler(self.onAnyEvent, events.Raw())

    async def start(self, main_channel: str) -> None:
        """Bot entrypoint"""
        self.logger.info('bot started')
        self.logger.info(
            'signed in as: %s', (await self.client.get_me()).stringify()
        )
        main_channel_input_entt = await self.client.get_input_entity(
            main_channel
        )
        self.main_channel = await self.client.get_entity(
            main_channel_input_entt
        )
        assert self.main_channel, "Main channel not found!"
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
            meme_folder_id: int = next(
                # we only check one for now
                filter(
                    lambda x: (isinstance(x, types.DialogFilter)
                                and x.title == self.memes_folder),
                    folders.filters,
                )
            #linter can't understand "isinstance(x, types.DialogFilter)"
            ).id # type: ignore
        except StopIteration:
            self.logger.warning(
                'Folder with name %s not found!', self.memes_folder
            )
            return -1
        self.logger.info('Meme folder id: %s', meme_folder_id)
        return meme_folder_id

    async def get_subscribed_channels(self) -> set[str]:
        # TODO: iter only in meme folder?
        subscribed = set()
        dialog: custom.dialog.Dialog
        async for dialog in self.client.iter_dialogs():
            self.logger.debug('Found dialog: %s\n\ttype: %s', dialog, type(dialog))
            if dialog.is_channel:
                subscribed.add(dialog)
        return subscribed

    async def _main(self) -> None:
        """main program loop: subscribe, restore info, get content,
        send content, save content"""

        self.channels, subscribed, meme_folder_id = await asyncio.gather(
            self._enumerate_channels(),
            self.get_subscribed_channels(),
            self.get_meme_folder_id(),
        )
        self.register_handlers()
        await self._subscribe_channels(self.channels, subscribed, meme_folder_id)
        await asyncio.Future()

    def _is_advertising_probably(self, msg_text: str, url: bool):
        """Do my best to filter out messages"""
        if url:
            # probably some advertisement link
            return False
        if len(msg_text) > 50:
            # too long for meme
            return False
        if '#' in msg_text:
            # probably some #adv tag
            return False
        return True

    async def _on_success_post(self, messages: list[custom.Message]) -> None:
        awaitables = []
        for msg in messages:
            awaitables.append(msg.mark_read())
        await asyncio.gather(*awaitables)

    async def _post_messages(self, messages: list[custom.Message], is_album=False) -> None:
        """Post messages to main_channel"""
        try:
            if is_album:
                # We can ignore type here, since captions is actually expected
                # to be iterable, but telethon is not bothering setting right types
                await self.client._send_album(self.main_channel, messages,
                                              [m.text for m in messages]) # type: ignore
                self.logger.debug('send album')
            else:
                message = messages[0] # only one message
                sendable_message = types.Message(
                    id=message.id,
                    peer_id=message.peer_id,
                    message=message.message or "",
                    date=message.date,
                    media=message.media
                )
                # self.main_channel is not None, we check it at `start`, and it is
                # not list, since we requested only on Entity there
                await self.client.send_message(self.main_channel,  # type: ignore
                                            sendable_message)
                self.logger.debug('send message:\n%s\n', sendable_message)
            await self._on_success_post(messages)
        except (telethon.errors.rpcbaseerrors.BadRequestError, TypeError) as err:
            self.logger.error("Can't send media: %s", err)
        except Exception as err: # something wrong, but I don't want to die here
            self.logger.error('Unexpected exception during message posting: %s', err)

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
        # TODO: subscribe asyncronously
        # TODO: move sucscribed chat to meme folder
        for channel in channels:
            info = f'{channel.title} (@{channel.username})'
            if channel.username in subscribed:
                if meme_folder_id >= 0:
                    futures.append(
                        self.client.edit_folder(channel, meme_folder_id))
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
                result: types.Updates = await self.client( # type: ignore
                                            JoinChannelRequest(ic))
                self.logger.debug(
                    'Joining channel result:\n\tres: %s\n\ttype: %s',
                    result.stringify(),
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
        asyncio.gather(*futures)
