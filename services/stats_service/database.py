import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

load_dotenv(find_dotenv())

# По умолчанию путь к общей базе данных заявок (requests.db в request_service)
CURRENT_DIR = Path(__file__).resolve().parent
DEFAULT_REQUESTS_DB = CURRENT_DIR.parent / "request_service" / "requests.db"
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_REQUESTS_DB.as_posix()}"

REQUESTS_DB_URL = os.getenv("REQUESTS_DB_URL", DEFAULT_DB_URL)

# stats-service использует базу данных только для чтения
engine = create_engine(
    REQUESTS_DB_URL,
    connect_args={"check_same_thread": False, "timeout": 15} if "sqlite" in REQUESTS_DB_URL else {},
)


class Base(DeclarativeBase):
    """Базовый класс для маппинга таблиц общей БД заявок"""
    pass


def get_db():
    """Генератор сессий чтения из базы данных заявок"""
    with Session(engine) as session:
        yield session
