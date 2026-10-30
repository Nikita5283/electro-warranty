import os
import logging
from logging.handlers import TimedRotatingFileHandler
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from clients import GatewayConfigSingleton
from patterns import GatewayFacade


os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("gateway")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = TimedRotatingFileHandler(
        filename="logs/gateway.log",
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
    config = GatewayConfigSingleton()
    app.state.http = httpx.AsyncClient(timeout=config.proxy_timeout, trust_env=False)
    mode = "заглушки (USE_MOCKS=true)" if config.use_mocks else "users-service"
    logger.info(f"API Gateway запущен. Проверка токенов: {mode}")
    yield
    await app.state.http.aclose()
    logger.info("API Gateway остановлен.")


app = FastAPI(
    title="API Gateway",
    description="Единая точка входа системы гарантийного обслуживания электротоваров",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=GatewayConfigSingleton().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    logger.info(f"Входящий запрос: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Ответ: {request.method} {request.url.path} -> {response.status_code}")
    return response


@app.get("/ping", tags=["System"])
async def ping():
    return {"status": "ok"}


@app.get("/health", tags=["System"])
async def health_check(request: Request):
    facade = GatewayFacade(request.app.state.http)
    return {"status": "ok", "service": "gateway", "services": await facade.services_health()}


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def proxy(request: Request):
    facade = GatewayFacade(request.app.state.http)
    return await facade.handle(request)
