import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def generate_short_id() -> str:
    """Генерирует id из 8 символов"""
    return uuid.uuid4().hex[:8].upper()


def utc_now() -> datetime:
    """Единая функция генерации времени строго в UTC без временных сдвигов"""
    return datetime.now(timezone.utc)


class ServiceRequestModel(Base):
    """Таблица для заявок на гарантийное обслуживание"""
    __tablename__ = "service_request"

    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generate_short_id)
    problem_description: Mapped[str] = mapped_column(String(500), nullable=False)
    purchase_id: Mapped[str] = mapped_column(String(8), nullable=False)
    client_id: Mapped[str] = mapped_column(String(8), nullable=False)
    product_id: Mapped[str | None] = mapped_column(String(8), nullable=True)
    employee_id: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    cell_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Связь один ко многим с историей статусов
    history: Mapped[List["StatusHistoryModel"]] = relationship(
        back_populates="service_request",
        cascade="all, delete-orphan",
        order_by="StatusHistoryModel.changed_at"
    )


class StatusHistoryModel(Base):
    """Таблица для хранения статусов заявок на гарантийное обслуживание"""
    __tablename__ = "status_history"

    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generate_short_id)
    request_id: Mapped[str] = mapped_column(String(8), ForeignKey("service_request.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    employee_id: Mapped[str | None] = mapped_column(String(8), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)

    service_request: Mapped["ServiceRequestModel"] = relationship(back_populates="history")
