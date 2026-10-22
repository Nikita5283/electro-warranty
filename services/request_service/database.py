import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

# url postgres бд
DATABSE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABSE_URL
)


class Base(DeclarativeBase):
    """Регистрирует все таблицы бд"""
    pass


def get_db():
    """Генератор сессий бд"""
    with Session(engine) as session:
        yield session