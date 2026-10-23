import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from typing import Optional, List, Dict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import ServiceRequestModel, StatusHistoryModel, utc_now
from clients import (
    PurchaseDomainInfo,
    PurchaseDataAdapter,
    ExternalClientFactory,
    LoggingClientProxy,
    BaseExternalClient,
)

logger = logging.getLogger("request-service")


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Приводит datetime к UTC для безопасного вычисления разницы во времени"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# поведенческий паттерн №1 chain of responsibility (Цепочка обязанностей)
# Последовательная проверка условий гарантии при создании заявки
class WarrantyValidationHandler(ABC):
    def __init__(self, next_handler: Optional["WarrantyValidationHandler"] = None):
        self._next = next_handler

    def handle(self, purchase: PurchaseDomainInfo, user_id: str) -> None:
        self._check(purchase, user_id)
        if self._next:
            self._next.handle(purchase, user_id)

    @abstractmethod
    def _check(self, purchase: PurchaseDomainInfo, user_id: str) -> None:
        pass


class OwnerValidationHandler(WarrantyValidationHandler):
    """Звено 1 Проверка владельца покупки"""
    def _check(self, purchase: PurchaseDomainInfo, user_id: str) -> None:
        if purchase.client_id != user_id:
            logger.warning(f"Отказ в создании заявки: клиент {user_id} не является владельцем покупки")
            raise HTTPException(status_code=422, detail="Вы не являетесь владельцем данной покупки")


class WarrantyDateValidationHandler(WarrantyValidationHandler):
    """Звено 2 Проверка даты окончания гарантии"""
    def _check(self, purchase: PurchaseDomainInfo, user_id: str) -> None:
        if purchase.warranty_until < date.today():
            logger.warning(f"Отказ в создании заявки: гарантия истекла ({purchase.warranty_until})")
            raise HTTPException(status_code=422, detail="Срок действия гарантии по данному товару истёк")


# поведенческий паттерн №2 state
# Обеспечивает строго последовательный переход заявки по статусам
class RequestState(ABC):
    status_name: str
    next_allowed_status: Optional[str]

    def validate_transition(self, target_status: str, cell_code: Optional[str]) -> None:
        if target_status != self.next_allowed_status:
            logger.warning(f"Попытка некорректного перехода статуса: '{self.status_name}' -> '{target_status}'")
            raise HTTPException(
                status_code=422,
                detail=f"Переход из статуса '{self.status_name}' в '{target_status}' запрещён. "
                       f"Следующий допустимый статус: '{self.next_allowed_status}'",
            )


class AcceptedState(RequestState):
    status_name = "принят"
    next_allowed_status = "товар принят в сервис"


class ReceivedInServiceState(RequestState):
    status_name = "товар принят в сервис"
    next_allowed_status = "товар на обслуживании"


class InMaintenanceState(RequestState):
    status_name = "товар на обслуживании"
    next_allowed_status = "товар обслужен"

    def validate_transition(self, target_status: str, cell_code: Optional[str]) -> None:
        super().validate_transition(target_status, cell_code)
        if not cell_code:
            raise HTTPException(
                status_code=400,
                detail="Для перевода в статус 'товар обслужен' необходимо указать код ячейки постамата (cell_code)",
            )


class ServicedState(RequestState):
    status_name = "товар обслужен"
    next_allowed_status = "товар выдан покупателю"


class IssuedState(RequestState):
    status_name = "товар выдан покупателю"
    next_allowed_status = None


STATE_MAP: Dict[str, RequestState] = {
    "принят": AcceptedState(),
    "товар принят в сервис": ReceivedInServiceState(),
    "товар на обслуживании": InMaintenanceState(),
    "товар обслужен": ServicedState(),
    "товар выдан покупателю": IssuedState(),
}


# Поведенческий паттерн №3 observer
# Автоматическое протоколирование в StatusHistory, лог и отправка в stats-service
class StatusObserver(ABC):
    @abstractmethod
    async def update(self, db: Session, req: ServiceRequestModel, comment: str) -> None:
        pass


class StatusHistoryDbObserver(StatusObserver):
    """Подписчик 1 Записывает событие в таблицу StatusHistory (протоколирование на 3 года)"""
    async def update(self, db: Session, req: ServiceRequestModel, comment: str) -> None:
        entry = StatusHistoryModel(
            request_id=req.id,
            status=req.status,
            employee_id=req.employee_id,
            comment=comment,
        )
        db.add(entry)


class AuditLogObserver(StatusObserver):
    """Подписчик 2 Пишет информацию о смене статуса в файловый лог"""
    async def update(self, db: Session, req: ServiceRequestModel, comment: str) -> None:
        logger.info(f"Протокол заявки {req.id}: статус='{req.status}', сотрудник={req.employee_id} ({comment})")


class StatsServiceObserver(StatusObserver):
    """Подписчик 3 Отправляет факт закрытия заявки в stats-service асинхронно"""
    def __init__(self, client: BaseExternalClient):
        self.client = client

    async def update(self, db: Session, req: ServiceRequestModel, comment: str) -> None:
        # По архплану отправляется только факт закрытия заявки, а stats-service читает общую БД
        if req.status == "товар выдан покупателю" or req.closed_at is not None:
            # Асинхронная отправка без ожидания ответа (fire-and-forget)
            asyncio.create_task(self._safe_notify(req.id))

    async def _safe_notify(self, request_id: str) -> None:
        try:
            await self.client.send_stats_event({"request_id": request_id})
        except Exception as exc:
            logger.error(f"Не удалось асинхронно уведомить stats-service о закрытии заявки {request_id}: {exc}")


# структурный паттерн №3 facade
# Единая точка входа в бизнес-логику для HTTP-эндпоинтов FastAPI
class RequestServiceFacade:
    def __init__(self, db: Session):
        self.db = db
        raw_client = ExternalClientFactory.create_client()
        self.client = LoggingClientProxy(raw_client)
        self.observers: List[StatusObserver] = [
            StatusHistoryDbObserver(),
            AuditLogObserver(),
            StatsServiceObserver(self.client),
        ]

    async def _notify_observers(self, req: ServiceRequestModel, comment: str) -> None:
        for observer in self.observers:
            await observer.update(self.db, req, comment)

    async def create_request(self, purchase_id: str, problem_description: str, user_id: str) -> ServiceRequestModel:
        # 1. Получение данных покупки через Proxy и преобразование через Adapter
        raw_purchase = await self.client.get_purchase(purchase_id)
        purchase_info = PurchaseDataAdapter(raw_purchase).to_domain()

        # 2. Проверка владельца и гарантии через Chain of Responsibility
        chain = OwnerValidationHandler(next_handler=WarrantyDateValidationHandler())
        chain.handle(purchase_info, user_id)

        # 3. Создание заявки со статусом "принят"
        new_req = ServiceRequestModel(
            purchase_id=purchase_id,
            client_id=user_id,
            product_id=purchase_info.product_id,
            problem_description=problem_description,
            status="принят",
        )
        self.db.add(new_req)
        self.db.flush()

        # 4. Уведомление всех Observers
        await self._notify_observers(new_req, comment="Заявка создана клиентом")
        self.db.commit()
        self.db.refresh(new_req)
        return new_req

    def list_requests(self, status_filter: Optional[str], client_id: Optional[str]) -> List[ServiceRequestModel]:
        stmt = select(ServiceRequestModel).order_by(ServiceRequestModel.created_at.desc())
        if status_filter:
            stmt = stmt.where(ServiceRequestModel.status == status_filter)
        if client_id:
            stmt = stmt.where(ServiceRequestModel.client_id == client_id)
        return list(self.db.scalars(stmt).all())

    def get_request(self, request_id: str) -> ServiceRequestModel:
        req = self.db.get(ServiceRequestModel, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        return req

    async def assign_employee(self, request_id: str, employee_id: str) -> ServiceRequestModel:
        req = self.get_request(request_id)
        req.employee_id = employee_id
        await self._notify_observers(req, comment=f"Заявка взята в работу сотрудником {employee_id}")
        self.db.commit()
        self.db.refresh(req)
        return req

    async def change_status(
        self,
        request_id: str,
        new_status: str,
        employee_id: Optional[str],
        cell_code: Optional[str],
        comment: Optional[str],
    ) -> ServiceRequestModel:
        req = self.get_request(request_id)

        # Проверка: сотрудник должен предварительно взять заявку в работу (assign)
        if not req.employee_id:
            logger.warning(f"Отказ в смене статуса заявки {request_id}: заявка не взята в работу сотрудником")
            raise HTTPException(
                status_code=400,
                detail="Нельзя изменить статус заявки: она ещё не взята в работу сотрудником (не назначен исполнитель через assign)",
            )

        # 1. Проверка перехода через паттерн State
        current_state = STATE_MAP.get(req.status)
        if not current_state:
            raise HTTPException(status_code=400, detail="Неизвестный текущий статус заявки")
        current_state.validate_transition(new_status, cell_code)

        # 2. Если требуется ячейка, занимаем её в locker-service через Proxy
        occupied_cell = None
        if new_status == "товар обслужен" and cell_code:
            code = await self.client.occupy_cell(cell_code, req.id)
            if code == 409:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ячейка {cell_code} уже занята, выберите другую свободную ячейку",
                )
            occupied_cell = cell_code
            req.cell_code = cell_code

        # 3. Сохранение нового статуса в БД с компенсацией при сбое
        try:
            released_cell = None
            if new_status == "товар выдан покупателю":
                released_cell = req.cell_code
                req.closed_at = utc_now()

            req.status = new_status
            if employee_id:
                req.employee_id = employee_id

            await self._notify_observers(req, comment=comment or f"Статус изменён на '{new_status}'")
            self.db.commit()
            self.db.refresh(req)

            # Освобождаем ячейку в locker-service только ПОСЛЕ успешного сохранения в БД
            if new_status == "товар выдан покупателю" and released_cell:
                await self.client.release_cell(released_cell, req.id)

            return req

        except Exception as exc:
            self.db.rollback()
            # Если ячейка была занята в locker-service, но сохранение в БД упало — освобождаем её
            if occupied_cell:
                try:
                    logger.warning(f"Откат занятия ячейки {occupied_cell} из-за ошибки сохранения в БД: {exc}")
                    await self.client.release_cell(occupied_cell, req.id)
                except Exception as rel_err:
                    logger.error(f"Не удалось освободить ячейку {occupied_cell} при откате: {rel_err}")
            raise
