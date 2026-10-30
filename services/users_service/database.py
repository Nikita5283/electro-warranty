import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

# Автоматически находит и загружает .env из корня проекта или текущей папки
load_dotenv(find_dotenv())

# Своя переменная окружения, чтобы не пересекаться с DATABASE_URL других сервисов
DEFAULT_DB_FILE = Path(__file__).resolve().parent / "users.db"
DATABASE_URL = os.getenv("USERS_DB_URL") or f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)


class Base(DeclarativeBase):
    """Регистрирует все таблицы бд users-service"""
    pass


def get_db():
    """Генератор сессий бд"""
    with Session(engine) as session:
        yield session
