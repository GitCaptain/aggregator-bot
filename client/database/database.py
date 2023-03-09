
from typing import Type

from sqlalchemy import ScalarResult, create_engine, select
from sqlalchemy.orm import Session

from .database_mappings import BaseORM


class Database:

    def __init__(self, path: str) -> None:
        self.engine = create_engine(f'sqlite+pysqlite:///{path}')
        BaseORM.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        return Session(self.engine)

    def insert(self, session: Session, object: BaseORM) -> None:
        session.add(object)

    def select(self, session: Session, cls: Type[BaseORM]) -> ScalarResult[BaseORM]:
        return session.scalars(select(cls))
