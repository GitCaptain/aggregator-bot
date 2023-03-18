
from typing import Type

from sqlalchemy import ScalarResult, Select, create_engine, select
from sqlalchemy.orm import Session

from .database_mappings import BaseORM


class Database:

    def __init__(self, path: str) -> None:
        self.engine = create_engine(f'sqlite+pysqlite:///{path}')
        BaseORM.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        return Session(self.engine)

    @staticmethod
    def insert(session: Session, object: BaseORM) -> None:
        session.add(object)

    @staticmethod
    def select(cls: Type[BaseORM]) -> Select[tuple[BaseORM]]:
        return select(cls)

    @staticmethod
    def execute_query(session: Session, query) -> ScalarResult[BaseORM]:
        return session.scalars(query)

    def select_result(self, session: Session, cls: Type[BaseORM]) -> ScalarResult[BaseORM]:
        return session.scalars(self.select(cls))
