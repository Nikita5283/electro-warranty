from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ServiceRequestModel(Base):
    """Модель заявки на гарантийное обслуживание (чтение из общей БД requests)"""
    __tablename__ = "service_request"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    problem_description: Mapped[str] = mapped_column(String(500), nullable=False)
    purchase_id: Mapped[str] = mapped_column(String(8), nullable=False)
    client_id: Mapped[str] = mapped_column(String(8), nullable=False)
    product_id: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    employee_id: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    cell_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    history: Mapped[List["StatusHistoryModel"]] = relationship(
        back_populates="service_request",
        order_by="StatusHistoryModel.changed_at",
    )


class StatusHistoryModel(Base):
    """Модель истории статусов заявки (чтение из общей БД requests)"""
    __tablename__ = "status_history"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(8), ForeignKey("service_request.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    employee_id: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    service_request: Mapped["ServiceRequestModel"] = relationship(back_populates="history")
