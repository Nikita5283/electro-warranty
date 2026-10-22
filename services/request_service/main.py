import os
import logging
from logging.handlers import TimedRotatingFileHandler
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, Depends, Header, Query, Request, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from schemas import (
    CreateRequestSchema,
    AssignRequestSchema,
    ChangeStatusSchema,
    ServiceRequestOut,
)
from patterns import RequestServiceFacade, STATE_MAP


# Настройка логирования
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("request-service")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = TimedRotatingFileHandler(
        filename="logs/request-service.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Автоматически создаем таблицы в БД при старте сервиса
    Base.metadata.create_all(bind=engine)
    logger.info("Микросервис request-service запущен.")
    yield
    logger.info("Микросервис request-service остановлен.")


app = FastAPI(
    title="Request Service",
    description="Микросервис гарантийных заявок",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    logger.info(f"Входящий запрос: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Ответ: {request.method} {request.url.path} -> {response.status_code}")
    return response


@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """Проверка состояния сервиса и его БД"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "service": "request-service"}
    except Exception as exc:
        logger.error(f"Ошибка подключения к БД: {exc}")
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/v1/requests/statuses", response_model=List[str], tags=["Requests"])
def get_statuses():
    """Справочник статусов жизненного цикла заявки"""
    return list(STATE_MAP.keys())


@app.post("/api/v1/requests", response_model=ServiceRequestOut, status_code=201, tags=["Requests"])
async def create_request(
    payload: CreateRequestSchema,
    x_user_id: str = Header("USER0001", alias="X-User-Id", description="ID пользователя от API Gateway"),
    db: Session = Depends(get_db),
):
    """Создание гарантийной заявки клиентом (проверка гарантии в catalog-service)"""
    facade = RequestServiceFacade(db)
    return await facade.create_request(payload.purchase_id, payload.problem_description, x_user_id)


@app.get("/api/v1/requests", response_model=List[ServiceRequestOut], tags=["Requests"])
def list_requests(
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    client_id: Optional[str] = Query(None, description="Фильтр по ID клиента"),
    db: Session = Depends(get_db),
):
    """Список заявок (очередь заявок для сотрудника сервиса или 'Мои заявки' для клиента)"""
    facade = RequestServiceFacade(db)
    return facade.list_requests(status, client_id)


@app.get("/api/v1/requests/{request_id}", response_model=ServiceRequestOut, tags=["Requests"])
def get_request(request_id: str, db: Session = Depends(get_db)):
    """Получение карточки заявки вместе с историей статусов StatusHistory"""
    facade = RequestServiceFacade(db)
    return facade.get_request(request_id)


@app.post("/api/v1/requests/{request_id}/assign", response_model=ServiceRequestOut, tags=["Requests"])
async def assign_request(
    request_id: str,
    payload: Optional[AssignRequestSchema] = None,
    x_user_id: Optional[str] = Header("EMP00001", alias="X-User-Id", description="ID сотрудника сервиса"),
    db: Session = Depends(get_db),
):
    """Взятие заявки из очереди в работу сотрудником сервиса"""
    emp_id = (payload.employee_id if payload and payload.employee_id else None) or x_user_id
    if not emp_id:
        raise HTTPException(status_code=400, detail="Не указан ID сотрудника")
    facade = RequestServiceFacade(db)
    return await facade.assign_employee(request_id, emp_id)


@app.post("/api/v1/requests/{request_id}/status", response_model=ServiceRequestOut, tags=["Requests"])
async def update_request_status(
    request_id: str,
    payload: ChangeStatusSchema,
    x_user_id: Optional[str] = Header("EMP00001", alias="X-User-Id", description="ID сотрудника сервиса"),
    db: Session = Depends(get_db),
):
    """Последовательный перевод заявки по статусам (с занятием и освобождением ячейки постамата)"""
    facade = RequestServiceFacade(db)
    return await facade.change_status(
        request_id=request_id,
        new_status=payload.status,
        employee_id=x_user_id,
        cell_code=payload.cell_code,
        comment=payload.comment,
    )