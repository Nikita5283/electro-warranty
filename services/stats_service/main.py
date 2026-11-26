import os
import logging
from logging.handlers import TimedRotatingFileHandler
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from patterns import StatsServiceFacade
from routers import stats_router

# Настройка логирования
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("stats-service")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = TimedRotatingFileHandler(
        filename="logs/stats-service.log",
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
    # Создаем таблицы в БД заявок, если они еще не были созданы, и при необходимости сидируем демо-данные
    try:
        Base.metadata.create_all(bind=engine)
        with Session(engine) as db:
            StatsServiceFacade(db).seed_demo_requests_if_empty()
    except Exception as exc:
        logger.warning(f"Предупреждение при инициализации requests_db: {exc}")

    logger.info("Микросервис stats-service запущен на порту 8005.")
    yield
    logger.info("Микросервис stats-service остановлен.")


app = FastAPI(
    title="Stats Service",
    description="Микросервис аналитической статистики и отчётности для руководителя сервисного центра",
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
    """Проверка состояния сервиса и доступности для чтения общей БД заявок"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "service": "stats-service"}
    except Exception as exc:
        logger.error(f"Ошибка доступа к requests_db в stats-service: {exc}")
        raise HTTPException(status_code=503, detail="Database unavailable")


# Подключение маршрутов
app.include_router(stats_router)
