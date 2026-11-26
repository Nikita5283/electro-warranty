import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

# Загрузка переменных окружения
load_dotenv(find_dotenv())

# Определение пути по умолчанию к SQLite базе данных
CURRENT_DIR = Path(__file__).resolve().parent
DEFAULT_DB_FILE = CURRENT_DIR / "catalog.db"
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"

DATABASE_URL = os.getenv("CATALOG_DB_URL", DEFAULT_DB_URL)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)


class Base(DeclarativeBase):
    """Базовый декларативный класс для моделей catalog-service"""
    pass


def get_db():
    """Генератор сессий SQLAlchemy для FastAPI Depends"""
    with Session(engine) as session:
        yield session
