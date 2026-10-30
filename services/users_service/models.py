import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

CLIENT = "CLIENT"
EMPLOYEE = "EMPLOYEE"
MANAGER = "MANAGER"
ADMIN = "ADMIN"
VALID_ROLES = {CLIENT, EMPLOYEE, MANAGER, ADMIN}


def generate_short_id() -> str:
    """Генерирует уникальный id из 8 символов"""
    return uuid.uuid4().hex[:8].upper()


def utc_now() -> datetime:
    """Единая функция генерации времени строго в UTC без временных сдвигов"""
    return datetime.now(timezone.utc)


class UserModel(Base):
    """Таблица пользователей системы"""
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generate_short_id)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=CLIENT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
