"""Main bot functions"""

import asyncio
import itertools
import logging
from hashlib import sha256
from typing import Iterable, Optional

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
from telethon.tl.types import (
    MessageEntityTextUrl,
    MessageMediaPhoto,
    TypeChat,
    TypeMessageMedia,
    Updates,
)


class ChannelUpd:
    """Channel model for use with telethon objects"""

    # pylint: disable=invalid-name
    # pylint: disable=too-few-public-methods

    def __init__(self, _id: int, username: str, latest_saved_msg_id: int,
                 entt: Optional[TypeChat] = None) -> None:
        self.id = _id
        self.username = username
        self.latest_saved_msg_id = latest_saved_msg_id
        self.entt = entt

    def __repr__(self) -> str:
        return f'<ChannelUpd object, id: {self.id}, username: {self.username}, ' \
               f'latest msg_id: {self.latest_saved_msg_id}, entt set: {self.entt is not None}>'


class MessageUpd:
    """Message model for use with telethon objects"""

    # pylint: disable=too-many-arguments
    # pylint: disable=too-few-public-methods

    def __init__(self, msg_id: int, msg_gruop_id: Optional[int], channel_id: int,
                 text: Optional[str], media_ref: Optional[TypeMessageMedia], media_bytes: bytes,
                 is_url: bool):
        # media_ref is internal telethon structure used to forward media.
        # media_bytes - downloaded media as bytes to calculate hash
        self.msg_id = msg_id
        self.group_id = msg_gruop_id
        self.channel_id = channel_id
        self.text = text
        self.media_ref = media_ref
        self.url = is_url
        self.sha256 = sha256(media_bytes).digest()

    def __repr__(self) -> str:
        return f'<MessageUPD object, msg_id: {self.msg_id}, channel_id: {self.channel_id}, ' \
               f'group_id: {self.group_id}, text: {self.text}>'


def merge_infos(db_info: list[ChannelUpd], tg_info: list[TypeChat]) -> list[ChannelUpd]:
    """Merge info from database with new one coming from telegram"""
    new_chats = []
    for tg_chat in tg_info:
        matched = False
        for db_chat in db_info:
            # TODO: check in usernameS maybe chat is renamed
            if tg_chat.username == db_chat.username:
                db_chat.entt = tg_chat
                matched = True
                break
        # Not matched - 2 variants:
        # 1 - channel removed from list of content providers - old info remains in database,
        # but it doesn't exists in current tg_info
        # 2 - channel added to content provider list and doesn't have database entry yet.
        # 1st case - only get channels from db that are currently in content provider
        # (fixed outside this function), 2nd - create new channel, that will be placed to database
        if not matched:
            new_chats.append(ChannelUpd(tg_chat.id, tg_chat.username, 0, tg_chat))
    assert all(ch.entt is not None for ch in new_chats + db_info)
    return new_chats

class Bot:
    """The bot which is downloading content from channels and repost it"""

    def __init__(self,
                 owner: 'app.App',
                 client: telethon.TelegramClient,
                 database: Database,
                 file_processor: FileProcessor) -> None:
        self.client = client
        self.file_processor = file_processor
        self.owner = owner
        self.logger = logging.getLogger('Main.bot')
        self.main_channel = None
        # pylint: disable=invalid-name
        self.me = None
        self.db = database

    async def start(self, main_channel: str) -> None:
        """Bot entrypoint"""
        self.logger.info('bot started')
        self.logger.debug('signed in as: %s', (await self.client.get_me()).stringify())
        main_channel_input_entt = await self.client.get_input_entity(main_channel)
        self.main_channel = await self.client.get_entity(main_channel_input_entt)
        sleep_time = 5 * 60 # 5 min
        await self._mainloop(sleep_time)

    def restore_info(self, session: Session, usernames: set[str]) -> list[ChannelUpd]:
        """Get info saved to database from previous runs
           We only need to get chats with usernames that are currently intresting
        """
        # TODO: optimize query
        self.logger.info('reading database')
        msgs = self.db.select_result(session, MessageMapping)
        channels = self.db.execute_query(session, self.db.select(ChannelMapping)
                                                    .filter(ChannelMapping.username.in_(usernames)))
        info = {}
        ch_map: ChannelMapping
        for ch_map in channels:
            self.logger.debug('get %s from database', ch_map)
            info[ch_map.id] = [ch_map.username, None]
        msg: MessageMapping
        for msg in msgs:
            self.logger.debug('get %s from database', msg)
            if info.get(msg.channel_id) and \
               (not info[msg.channel_id][1] or info[msg.channel_id][1] < msg.msg_id):
                info[msg.channel_id][1] = msg.msg_id

        return [ChannelUpd(ch_id, *ch_info) for ch_id, ch_info in info.items()]

    def save_info(self, session: Session, channels: list[ChannelUpd],
                  messages: list[list[MessageUpd]]) -> None:
        """Save info about new messages to database"""
        self.logger.info('update database')
        for channel in channels:
            ch_map = ChannelMapping(id=channel.id, username=channel.username)
            self.logger.debug('save %s to database', ch_map)
            self.db.insert(session, ch_map)
        for msg_group in messages:
            for msg in msg_group:
                msg_map = MessageMapping(msg_id=msg.msg_id, group_id=msg.group_id,
                                         channel_id=msg.channel_id, hash=msg.sha256)
                self.logger.debug('save %s to database', msg_map)
                self.db.insert(session, msg_map)

    async def _mainloop(self, sleep_time: float) -> None:
        """main program loop: subscribe, restore info, get content, send content, save content"""
        while True:
            channels = await self._enumerate_channels()
            usernames = set(channel.username for channel in channels)
            await self._subscribe_channels(channels, usernames)
            with self.db.get_session() as db_session, db_session.begin():
                db_channels = self.restore_info(db_session, usernames)
                new_channels = merge_infos(db_channels, channels)
                channels = new_channels + db_channels
                messages = []
                for ch_info in channels:
                    messages.extend(await self._get_messages_since_id(ch_info.entt,
                                                                      ch_info.latest_saved_msg_id))
                await self._post_messages(messages, db_session)
                self.save_info(db_session, new_channels, messages)
                db_session.commit()
            self.logger.debug('sleep %ss', sleep_time)
            await asyncio.sleep(sleep_time)

    async def _get_messages_since_id(self, channel: TypeChat, msg_id: int = 0) \
        -> list[list[MessageUpd]]:
        """Get messages from channel starting from msg_id"""
        messages = []
        # fetch 10 latest message (max in one group)
        limit = 10
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
            try:
                urls = msg.get_entities_text(MessageEntityTextUrl)
                media_b: bytes = await msg.download_media(file=bytes)
                m_upd = MessageUpd(msg.id, msg.grouped_id, channel.id, msg.text, msg.media, media_b,
                                   bool(urls))
                messages[-1].append(m_upd)
            except ValueError as v:
                self.logger.error('Unknown message media type: %s, err: %s', type(msg.media), v)
        return messages

    def _get_posted(self, hashes: Iterable[bytes], db_session: Session) -> set[bytes]:
        """Select only those hashes from hashes, which exists in database"""
        return frozenset(self.db.execute_query(db_session,
                                               self.db.select(MessageMapping.hash)
                                                      .filter(MessageMapping.hash.in_(hashes)))
                                                      .all())

    def _is_text_ok(self, msg_text: str, url: bool):
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

    async def _post_messages(self, messages: list[list[MessageUpd]], db_session: Session) -> None:
        """Post messages to main_channel"""
        posted = self._get_posted(map(lambda msg: msg.sha256,
                                      itertools.chain.from_iterable(messages)),
                                  db_session)
        # Post in reverse order, since we add latest messages to the end of list
        for msg_group in messages[::-1]:
            # do not post messages if full group posted already
            # if only some messages from the group exist - it may be new meme
            if set(map(lambda msg: msg.sha256, msg_group)).issubset(posted):
                continue
            text = ''
            files = []
            url = False
            for msg in msg_group[::-1]:
                text = msg.text or text
                url = msg.url or url
                files.append(msg.media_ref)
            if not self._is_text_ok(text, url):
                # do not post this message, but save it to db to filter it out on the previous step.
                continue
            try:
                await self.client.send_file(self.main_channel, files, caption=text)
            except (telethon.errors.rpcbaseerrors.BadRequestError, TypeError) as err:
                self.logger.error("Can't send media: %s", err)

    async def _enumerate_channels(self) -> list[TypeChat]:
        """Get already subscribed channels"""
        channels_username = self.file_processor.channel_generator()
        channels = []
        tme_prefix='https://t.me/'
        joinchat='joinchat/'
        for channel_uname in channels_username:
            if channel_uname.startswith(tme_prefix):
                # TODO: how to manage closed channels?
                # i.e. what to use instead of username? hash?
                link = channel_uname\
                        .replace(tme_prefix, '').replace(joinchat, '', 1).replace('+', '', 1)
                self.logger.debug('trying to joing via link: %s', link)
                try:
                    upd: Updates = await self.client(ImportChatInviteRequest(link))
                    self.logger.debug('get upd from private channel: %s', upd.stringify())
                    # channels.append(upd) ??
                except (telethon.errors.rpcerrorlist.InviteHashExpiredError,
                        telethon.errors.rpcerrorlist.InviteHashEmptyError,
                        telethon.errors.rpcerrorlist.InviteHashInvalidError,
                        telethon.errors.rpcerrorlist.UserAlreadyParticipantError,
                        telethon.errors.rpcerrorlist.InviteRequestSentError,) as err:
                    self.logger.error('Error while trying to join private channel: %s', err)
            else:
                try:
                    ent = await self.client.get_input_entity(channel_uname)
                    channels.append(await self.client.get_entity(ent))
                except ValueError:
                    self.logger.error("Can't find input_entity for channel: %s", channel_uname)
        return channels

    async def _subscribe_channels(self, channels: list[TypeChat], subscribed: set[str]) -> None:
        """Subscribe to channels"""
        err_msg = 'Unable to join channel: %s, reason: %s'
        # TODO: Mute and archive all chats
        for channel in channels:
            info = f'{channel.title} (@{channel.username})'
            if channel.username in subscribed:
                self.logger.debug('skip channel %s, already subscribed', info)
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
