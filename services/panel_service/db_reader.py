import sqlite3
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, func, or_, cast, String, Table, MetaData
from sqlalchemy.engine import make_url


def to_json_value(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return f"<{len(value)} байт>"
    return value


# Порождающий паттерн №2 factory method
# Создает читателя БД под нужную СУБД; изменения в базу никогда не пишутся
class BaseDatabaseReader(ABC):
    def __init__(self, url: str):
        self.url = url
        self._engine = None

    @abstractmethod
    def exists(self) -> bool:
        pass

    @abstractmethod
    def _create_engine(self):
        pass

    def engine(self):
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    def tables(self) -> list:
        insp = inspect(self.engine())
        result = []
        for name in insp.get_table_names():
            columns = []
            for col in insp.get_columns(name):
                columns.append({"name": col["name"], "type": str(col["type"])})
            table = Table(name, MetaData(), autoload_with=self.engine())
            with self.engine().connect() as conn:
                count = conn.execute(select(func.count()).select_from(table)).scalar()
            result.append({"name": name, "columns": columns, "rows": count})
        return result

    def rows(self, table_name: str, search: str, limit: int, offset: int) -> dict:
        table = Table(table_name, MetaData(), autoload_with=self.engine())
        query = select(table)
        count_query = select(func.count()).select_from(table)

        if search:
            conditions = []
            for column in table.columns:
                conditions.append(cast(column, String).ilike(f"%{search}%"))
            query = query.where(or_(*conditions))
            count_query = count_query.where(or_(*conditions))

        query = query.limit(limit).offset(offset)
        with self.engine().connect() as conn:
            total = conn.execute(count_query).scalar()
            result = conn.execute(query)
            columns = list(result.keys())
            rows = []
            for row in result:
                rows.append([to_json_value(value) for value in row])
        return {"columns": columns, "rows": rows, "total": total}


class SqliteReader(BaseDatabaseReader):
    def _path(self) -> Path:
        return Path(make_url(self.url).database)

    def exists(self) -> bool:
        return self._path().is_file()

    def _create_engine(self):
        path = self._path().as_posix()

        def connect():
            return sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)

        return create_engine("sqlite://", creator=connect)


class ServerDatabaseReader(BaseDatabaseReader):
    def exists(self) -> bool:
        try:
            with self.engine().connect():
                return True
        except Exception:
            return False

    def _create_engine(self):
        return create_engine(self.url, pool_pre_ping=True, connect_args={"connect_timeout": 2})


class DatabaseReaderFactory:
    @staticmethod
    def create_reader(url: str) -> BaseDatabaseReader:
        if url.startswith("sqlite"):
            return SqliteReader(url)
        return ServerDatabaseReader(url)
