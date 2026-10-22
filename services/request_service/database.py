import os
from dotenv import load_dotenv, find_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

# Автоматически находит и загружает .env из корня проекта или текущей папки
load_dotenv(find_dotenv())

# Читаем переменную окружения; если она не найдена — оставляем резервный дефолт
DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./requests.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)


class Base(DeclarativeBase):
    """Регистрирует все таблицы бд"""
    pass


def get_db():
    """Генератор сессий бд"""
    with Session(engine) as session:
        yield session