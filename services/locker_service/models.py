import uuid
from datetime import datetime
from typing import List

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.orm import mapped_column

from database import Base


FREE = "FREE"
OCCUPIED = "OCCUPIED"


def generate_short_id() -> str:
    """Генерирует id из 8 символов"""
    return uuid.uuid4().hex[:8].upper()


class CellModel(Base):
    """Таблица ячеек постамата"""
    __tablename__ = "cell"

    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generate_short_id)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=FREE)

    # Связь один ко многим с назначениями ячейки
    assignments: Mapped[List["CellAssignmentModel"]] = relationship(
        back_populates="cell",
        order_by="CellAssignmentModel.assigned_at",
    )

    @property
    def active_assignment(self) -> "CellAssignmentModel | None":
        for assignment in self.assignments:
            if assignment.released_at is None:
                return assignment
        return None

    @property
    def request_id(self) -> str | None:
        """Заявка, под которую сейчас занята ячейка"""
        active = self.active_assignment
        return active.request_id if active else None


class CellAssignmentModel(Base):
    """Таблица назначений ячеек заявкам"""
    __tablename__ = "cell_assignment"

    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generate_short_id)
    cell_id: Mapped[str] = mapped_column(String(8), ForeignKey("cell.id"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(8), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    cell: Mapped["CellModel"] = relationship(back_populates="assignments")


class AuditLogModel(Base):
    """Протокол изменений справочника ячеек (хранение 3 года)"""
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(8), primary_key=True, default=generate_short_id)
    entity: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(8), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    changed_by: Mapped[str | None] = mapped_column(String(8), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
