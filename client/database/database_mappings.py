
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseORM(DeclarativeBase):
    pass


class Channel(BaseORM):

    __tablename__ = 'channels'

    # Channel name might change, but should be unique anyway
    # So use id as primary key, and update username if needed
    # TODO: what if one of the saved channels renamed and other one takes its previous name??

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)

    def __repr__(self) -> str:
        return f'<Channel object, id: {self.id}, username: {self.username}>'


class Message(BaseORM):

    __tablename__ = 'messages'

    id: Mapped[int] = mapped_column(primary_key=True)
    msg_id: Mapped[int]
    group_id = Mapped[Optional[int]]
    channel_id: Mapped[int] = mapped_column(ForeignKey('channels.id'))
    hash: Mapped[Optional[bytes]]

    def __repr__(self) -> str:
        return f'<Message object, id: {self.id}, msg_id: {self.msg_id}, ' \
               f'group_id: {self.group_id}, channel_id: {self.channel_id}>'
