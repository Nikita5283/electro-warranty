import os
import logging
from logging.handlers import TimedRotatingFileHandler
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from routers import router as requests_router


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


# Подключение роутера гарантийных заявок
app.include_router(requests_router)
