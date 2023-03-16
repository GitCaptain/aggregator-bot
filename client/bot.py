import asyncio
import logging
import os
from hashlib import sha256
from typing import Optional

import app
import telethon
from database.database import Database
from database.database_mappings import Channel as ChannelMapping
from database.database_mappings import Message as MessageMapping
from file_processor import FileProcessor
from sqlalchemy.orm import Session
from telethon.errors import (
    ChannelIdInvalidError,
    ChannelPrivateError,
    ChannelsTooMuchError,
    InviteRequestSentError,
)
from telethon.tl.custom.message import Message
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import MessageMediaPhoto, TypeChat, TypeMessageMedia, Updates


class ChannelUpd:

    def __init__(self, id: int, username: str, latest_saved_msg_id: int,
                 entt: Optional[TypeChat] = None) -> None:
        self.id = id
        self.username = username
        self.latest_saved_msg_id = latest_saved_msg_id
        self.entt = entt

    def __repr__(self) -> str:
        return f'<ChannelUpd object, id: {self.id}, username: {self.username}, ' \
               f'latest msg_id: {self.latest_saved_msg_id}, entt set: {self.entt is not None}>'


class MessageUpd:

    def __init__(self, msg_id: int, msg_gruop_id: Optional[int], channel_id: int,
                 text: Optional[str], media: Optional[TypeMessageMedia]):
        self.msg_id = msg_id
        self.group_id = msg_gruop_id
        self.channel_id = channel_id
        self.text = text
        self.media = media

    def __repr__(self) -> str:
        return f'<MessageUPD object, msg_id: {self.msg_id}, channel_id: {self.channel_id}, ' \
               f'group_id: {self.group_id}, text: {self.text}>'


def merge_infos(db_info: list[ChannelUpd], tg_info: list[TypeChat]) -> list[ChannelUpd]:
    new_chats = []
    for tg_chat in tg_info:
        matched = False
        for db_chat in db_info:
            # TODO: check in usernameS maybe chat is renamed
            if tg_chat.username == db_chat.username:
                db_chat.entt = tg_chat
                matched = True
                break
        if not matched:
            new_chats.append(ChannelUpd(tg_chat.id, tg_chat.username, 0, tg_chat))
    # TODO: channel deleted from file ? remove assert
    assert all(ch.entt is not None for ch in new_chats + db_info)
    return new_chats

class Bot:

    def __init__(self,
                 owner: 'app.App',
                 client: telethon.TelegramClient,
                 database: Database,
                 file_processor: FileProcessor) -> None:
        self.client = client
        self.file_processor = file_processor
        self.owner = owner
        self.logger = logging.getLogger('Main.bot')
        self.me = None
        self.main_channel = None
        self.db = database

    async def start(self, main_channel: str) -> None:
        self.logger.info('bot started')
        self.logger.debug('signed in as: %s', (await self.client.get_me()).stringify())
        main_channel_input_entt = await self.client.get_input_entity(main_channel)
        self.main_channel = await self.client.get_entity(main_channel_input_entt)
        sleep_time = 5 * 60 # 5 min
        await self._mainloop(sleep_time)

    def restore_info(self, session: Session) -> list[ChannelUpd]:
        # TODO: optimize query
        self.logger.info('reading database')
        msgs = self.db.select(session, MessageMapping)
        channels = self.db.select(session, ChannelMapping)
        info = {}
        ch_map: ChannelMapping
        for ch_map in channels:
            self.logger.debug(f'get {ch_map} from database')
            info[ch_map.id] = [ch_map.username, None]
        msg: MessageMapping
        for msg in msgs:
            self.logger.debug(f'get {msg} from database')
            if not info[msg.channel_id][1] or info[msg.channel_id][1] < msg.msg_id:
                info[msg.channel_id][1] = msg.msg_id

        return [ChannelUpd(ch_id, *ch_info) for ch_id, ch_info in info.items()]

    def save_info(self, session: Session, channels: list[ChannelUpd],
                  messages: list[list[MessageUpd]]) -> None:
        self.logger.info('update database')
        for channel in channels:
            ch_map = ChannelMapping(id=channel.id, username=channel.username)
            self.logger.debug(f'save {ch_map} to database')
            self.db.insert(session, ch_map)
        for msg_group in messages:
            for msg in msg_group:
                # not sure if this is what I need to save
                # https://core.telegram.org/api/file_reference
                if isinstance(msg.media, MessageMediaPhoto):
                    file_ref = msg.media.photo.file_reference
                else:
                    file_ref = msg.media.document.file_reference
                msg_map = MessageMapping(msg_id=msg.msg_id, group_id=msg.group_id,
                                         channel_id=msg.channel_id, hash=sha256(file_ref).digest())
                self.logger.debug(f'save {msg_map} to database')
                self.db.insert(session, msg_map)

    async def _mainloop(self, sleep_time: float) -> None:
        while True:
            channels = await self._enumerate_channels()
            usernames = set(channel.username for channel in channels)
            await self._subscribe_channels(channels, usernames)
            with self.db.get_session() as db_session, db_session.begin():
                db_channels = self.restore_info(db_session)
                new_channels = merge_infos(db_channels, channels)
                channels = new_channels + db_channels
                messages = []
                for ch_info in channels:
                    messages.extend(await self._get_messages_since_id(ch_info.entt,
                                                                      ch_info.latest_saved_msg_id))
                await self._post_messages(messages)
                self.save_info(db_session, new_channels, messages)
                db_session.commit()
            self.logger.debug(f'sleep {sleep_time}s')
            await asyncio.sleep(sleep_time)

    async def _get_messages_since_id(self, channel: TypeChat, msg_id: int = 0) \
        -> list[list[MessageUpd]]:
        messages = []
        # fetch all messages (but no more then 3000) if we already have something from this channel,
        # else fetch 10 latest message (max in one group) only
        limit = 3000 if msg_id else 10
        last_grouped_id = None
        msg: Message
        async for msg in self.client.iter_messages(channel, limit=limit, min_id=msg_id):
            logging.debug('get msg from chat %s, msg:', channel.title)
            logging.debug(msg.stringify())
            if not msg.video and not msg.photo and not msg.gif:
                logging.debug('Msg with id %s: is not photo, video or gif', msg.id)
                continue
            if msg.grouped_id is None or msg.grouped_id != last_grouped_id:
                last_grouped_id = msg.grouped_id
                messages.append([])
            messages[-1].append(MessageUpd(msg.id, msg.grouped_id, channel.id, msg.text, msg.media))
        return messages

    async def _post_messages(self, messages: list[list[MessageUpd]]) -> None:
        # TODO: check messages are not posted before
        # Post in reverse order, since we add latest messages to the end of list
        for msg_group in messages[::-1]:
            text = ''
            files = []
            for msg in msg_group[::-1]:
                text = msg.text or text
                files.append(msg.media)
            await self.client.send_file(self.main_channel, files, caption=text)

    async def _enumerate_channels(self) -> list[TypeChat]:
        channels_username = self.file_processor.channel_generator()
        channels = []
        tme_prefix='https://t.me/'
        joinchat='joinchat/'
        for channel_uname in channels_username:
            if channel_uname.startswith(tme_prefix):
                # TODO: how to manage closed channels?
                # i.e. what to use instead of username? hash?
                link = channel_uname.replace(tme_prefix, '').replace(joinchat, '', 1).replace('+', '', 1)
                self.logger.debug('trying to joing via link: %s', link)
                try:
                    upd: Updates = await self.client(ImportChatInviteRequest(link))
                    self.logger.debug('get upd from private channel: %s', upd.stringify())
                    # channels.append(upd) ??
                except (telethon.errors.rpcerrorlist.InviteHashExpiredError,
                        telethon.errors.rpcerrorlist.InviteHashEmptyError,
                        telethon.errors.rpcerrorlist.InviteHashInvalidError,
                        telethon.errors.rpcerrorlist.UserAlreadyParticipantError,
                        telethon.errors.rpcerrorlist.InviteRequestSentError,) as e:
                    self.logger.error('Error while trying to join private channel: %s', e)
            else:
                try:
                    ent = await self.client.get_input_entity(channel_uname)
                    channels.append(await self.client.get_entity(ent))
                except ValueError:
                    self.logger.error("Can't find input_entity for channel: %s", channel_uname)
        return channels

    async def _subscribe_channels(self, channels: list[TypeChat], subscribed: set[str]) -> None:

        err_msg = 'Unable to join channel: %s, reason: %s'
        # TODO: Mute and archive all chats
        for channel in channels:
            info = f'{channel.title} (@{channel.username})'
            if channel.username in subscribed:
                self.logger.debug(f'skip channel {info}, already subscribed')
                continue
            try:
                result = await self.client(JoinChannelRequest(channel))
                self.logger.info('Join channel request result: %s', result.stringify())
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
