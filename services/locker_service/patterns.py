import os
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from models import CellModel, CellAssignmentModel, AuditLogModel, FREE, OCCUPIED

logger = logging.getLogger("locker-service")

DEFAULT_SEED_CELLS = "A-101,A-102,A-103,A-104,A-105,B-201,B-202,B-203,B-204,B-205"


# Порождающий паттерн №1 singleton
# Гарантирует единственный экземпляр конфигурации микросервиса в памяти
class LockerConfigSingleton:
    _instance: Optional["LockerConfigSingleton"] = None

    def __new__(cls) -> "LockerConfigSingleton":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            raw_codes = os.getenv("SEED_CELLS", DEFAULT_SEED_CELLS)
            cls._instance.seed_cells = [code.strip() for code in raw_codes.split(",") if code.strip()]
        return cls._instance


class CellEvent:
    """Факт изменения ячейки, который получают все подписчики"""
    def __init__(self, action: str, cell: CellModel, old_status: Optional[str],
                 request_id: Optional[str] = None, user_id: Optional[str] = None):
        self.action = action
        self.cell = cell
        self.old_status = old_status
        self.request_id = request_id
        self.user_id = user_id


# Поведенческий паттерн №1 state
# Определяет, что можно сделать с ячейкой в текущем статусе
class CellState(ABC):
    status_name: str

    @abstractmethod
    def occupy(self, cell: CellModel, request_id: str) -> bool:
        """Возвращает True, если статус ячейки нужно изменить"""
        pass

    @abstractmethod
    def release(self, cell: CellModel, request_id: str) -> bool:
        pass


class FreeState(CellState):
    status_name = FREE

    def occupy(self, cell: CellModel, request_id: str) -> bool:
        return True

    def release(self, cell: CellModel, request_id: str) -> bool:
        # Повторное освобождение не ошибка: ячейка уже свободна
        return False


class OccupiedState(CellState):
    status_name = OCCUPIED

    def occupy(self, cell: CellModel, request_id: str) -> bool:
        if cell.request_id == request_id:
            # Повторный запрос от той же заявки
            return False
        logger.warning(f"Отказ: ячейка {cell.code} уже занята заявкой {cell.request_id}, запрос от заявки {request_id}")
        raise HTTPException(status_code=409, detail=f"Ячейка {cell.code} уже занята")

    def release(self, cell: CellModel, request_id: str) -> bool:
        if cell.request_id != request_id:
            logger.warning(f"Отказ: ячейка {cell.code} занята заявкой {cell.request_id}, освободить просит заявка {request_id}")
            raise HTTPException(status_code=409, detail=f"Ячейка {cell.code} занята другой заявкой")
        return True


STATE_MAP: Dict[str, CellState] = {
    FREE: FreeState(),
    OCCUPIED: OccupiedState(),
}


# Поведенческий паттерн №2 observer
# Запись CellAssignment, протокол audit_log и файловый лог при каждом изменении ячейки
class CellObserver(ABC):
    @abstractmethod
    def update(self, db: Session, event: CellEvent) -> None:
        pass


class CellAssignmentObserver(CellObserver):
    """Подписчик 1 Открывает и закрывает назначение ячейки заявке"""
    def update(self, db: Session, event: CellEvent) -> None:
        if event.action == "occupy":
            db.add(CellAssignmentModel(cell=event.cell, request_id=event.request_id))
        elif event.action == "release":
            active = event.cell.active_assignment
            if active:
                active.released_at = datetime.now()


class AuditLogDbObserver(CellObserver):
    """Подписчик 2 Пишет изменение в таблицу audit_log"""
    def update(self, db: Session, event: CellEvent) -> None:
        new_value = event.cell.status
        if event.request_id:
            new_value = f"{event.cell.status} ({event.request_id})"
        db.add(AuditLogModel(
            entity="cell",
            entity_id=event.cell.id,
            action=event.action,
            old_value=event.old_status,
            new_value=new_value,
            changed_by=event.user_id,
        ))


class FileLogObserver(CellObserver):
    """Подписчик 3 Пишет изменение в файловый лог"""
    def update(self, db: Session, event: CellEvent) -> None:
        logger.info(
            f"Протокол ячейки {event.cell.code}: {event.action}, "
            f"статус {event.old_status} -> {event.cell.status}, заявка={event.request_id}"
        )


# Структурный паттерн №1 facade
# Единая точка входа в бизнес-логику для HTTP-эндпоинтов FastAPI
class LockerServiceFacade:
    def __init__(self, db: Session):
        self.db = db
        self.observers: List[CellObserver] = [
            CellAssignmentObserver(),
            AuditLogDbObserver(),
            FileLogObserver(),
        ]

    def _notify_observers(self, event: CellEvent) -> None:
        for observer in self.observers:
            observer.update(self.db, event)

    def _get_cell(self, code: str, for_update: bool = False) -> CellModel:
        stmt = select(CellModel).where(CellModel.code == code).options(selectinload(CellModel.assignments))
        if for_update:
            # Блокировка строки в PostgreSQL, чтобы две заявки не заняли одну ячейку
            stmt = stmt.with_for_update()
        cell = self.db.scalars(stmt).first()
        if not cell:
            logger.warning(f"Ячейка {code} не найдена")
            raise HTTPException(status_code=404, detail=f"Ячейка {code} не найдена")
        return cell

    def seed_cells(self) -> None:
        """Заполняет пустой справочник ячеек при первом запуске"""
        if self.db.scalars(select(CellModel).limit(1)).first():
            return
        for code in LockerConfigSingleton().seed_cells:
            cell = CellModel(code=code, status=FREE)
            self.db.add(cell)
            self.db.flush()
            self._notify_observers(CellEvent("create", cell, None, user_id="SYSTEM"))
        self.db.commit()

    def list_cells(self, status_filter: Optional[str]) -> List[CellModel]:
        stmt = select(CellModel).options(selectinload(CellModel.assignments)).order_by(CellModel.code)
        if status_filter:
            stmt = stmt.where(CellModel.status == status_filter)
        return list(self.db.scalars(stmt).all())

    def create_cell(self, code: str, user_id: Optional[str]) -> CellModel:
        cell = CellModel(code=code, status=FREE)
        self.db.add(cell)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            logger.warning(f"Отказ: ячейка {code} уже есть в справочнике")
            raise HTTPException(status_code=409, detail=f"Ячейка {code} уже существует")
        self._notify_observers(CellEvent("create", cell, None, user_id=user_id))
        self.db.commit()
        self.db.refresh(cell)
        return cell

    def occupy_cell(self, code: str, request_id: str) -> CellModel:
        cell = self._get_cell(code, for_update=True)
        old_status = cell.status
        if STATE_MAP[cell.status].occupy(cell, request_id):
            cell.status = OCCUPIED
            self._notify_observers(CellEvent("occupy", cell, old_status, request_id=request_id))
            self.db.commit()
            self.db.refresh(cell)
        return cell

    def release_cell(self, code: str, request_id: str) -> CellModel:
        cell = self._get_cell(code, for_update=True)
        old_status = cell.status
        if STATE_MAP[cell.status].release(cell, request_id):
            cell.status = FREE
            self._notify_observers(CellEvent("release", cell, old_status, request_id=request_id))
            self.db.commit()
            self.db.refresh(cell)
        return cell
