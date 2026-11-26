import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def generate_short_id() -> str:
    """Генерирует id из 8 символов (в верхнем регистре)"""
    return uuid.uuid4().hex[:8].upper()


def utc_now() -> datetime:
    """Возвращает текущую временную метку в UTC"""
    return datetime.now(timezone.utc)


class ProductModel(Base):
    """Таблица товаров магазина электротоваров"""
    __tablename__ = "product"

    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generate_short_id)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    warranty_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # Связь с покупками этого товара
    purchases: Mapped[List["PurchaseModel"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )


class PurchaseModel(Base):
    """Таблица покупок клиентов с фиксацией срока гарантии"""
    __tablename__ = "purchase"

    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generate_short_id)
    product_id: Mapped[str] = mapped_column(String(8), ForeignKey("product.id"), nullable=False)
    client_id: Mapped[str] = mapped_column(String(8), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(50), nullable=False)
    purchase_date: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    warranty_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    product: Mapped["ProductModel"] = relationship(back_populates="purchases")


class AuditLogModel(Base):
    """Таблица протоколирования изменений справочника товаров (раздел 9 ПР)"""
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generate_short_id)
    entity: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(8), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    changed_by: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
