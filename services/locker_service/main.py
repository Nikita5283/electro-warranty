import os
import logging
from logging.handlers import TimedRotatingFileHandler
from contextlib import asynccontextmanager
from typing import Optional, List, Literal

from fastapi import FastAPI, Depends, Header, Query, Request, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from schemas import CreateCellSchema, CellActionSchema, CellOut
from patterns import LockerServiceFacade


# Настройка логирования
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("locker-service")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = TimedRotatingFileHandler(
        filename="logs/locker-service.log",
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
    # Создаем таблицы и заполняем справочник ячеек при первом запуске
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        LockerServiceFacade(db).seed_cells()
    logger.info("Микросервис locker-service запущен.")
    yield
    logger.info("Микросервис locker-service остановлен.")


app = FastAPI(
    title="Locker Service",
    description="Микросервис ячеек постамата",
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
        return {"status": "ok", "service": "locker-service"}
    except Exception as exc:
        logger.error(f"Ошибка подключения к БД: {exc}")
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/v1/cells", response_model=List[CellOut], tags=["Cells"])
def list_cells(
    status: Optional[Literal["FREE", "OCCUPIED"]] = Query(None, description="Фильтр по статусу ячейки"),
    db: Session = Depends(get_db),
):
    """Список ячеек постамата (свободные ячейки для сотрудника сервиса: ?status=FREE)"""
    return LockerServiceFacade(db).list_cells(status)


@app.post("/api/v1/cells", response_model=CellOut, status_code=201, tags=["Cells"])
def create_cell(
    payload: CreateCellSchema,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id", description="ID администратора от API Gateway"),
    db: Session = Depends(get_db),
):
    """Добавление ячейки в справочник (администратор)"""
    return LockerServiceFacade(db).create_cell(payload.code, x_user_id)


@app.post("/internal/cells/{code}/occupy", response_model=CellOut, tags=["Internal"])
def occupy_cell(code: str, payload: CellActionSchema, db: Session = Depends(get_db)):
    """Занять ячейку под заявку (вызывает request-service). 409, если ячейка занята другой заявкой"""
    return LockerServiceFacade(db).occupy_cell(code, payload.request_id)


@app.post("/internal/cells/{code}/release", response_model=CellOut, tags=["Internal"])
def release_cell(code: str, payload: CellActionSchema, db: Session = Depends(get_db)):
    """Освободить ячейку после выдачи товара (вызывает request-service)"""
    return LockerServiceFacade(db).release_cell(code, payload.request_id)
