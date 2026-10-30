import os
import logging
from logging.handlers import TimedRotatingFileHandler
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from patterns import UsersServiceFacade
from routers import auth_router, users_router, internal_router


# Настройка логирования
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("users-service")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = TimedRotatingFileHandler(
        filename="logs/users-service.log",
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
    # Создаем таблицы и инициализируем тестовых пользователей
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        UsersServiceFacade(db).seed_default_users()
    logger.info("Микросервис users-service запущен.")
    yield
    logger.info("Микросервис users-service остановлен.")


app = FastAPI(
    title="Users Service",
    description="Микросервис пользователей и аутентификации",
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
    """Проверка состояния сервиса и доступности его базы данных"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "service": "users-service"}
    except Exception as exc:
        logger.error(f"Ошибка подключения к БД users-service: {exc}")
        raise HTTPException(status_code=503, detail="Database unavailable")


# Подключение маршрутов
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(internal_router)
