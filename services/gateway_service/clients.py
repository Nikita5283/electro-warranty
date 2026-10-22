import os
import logging
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from dotenv import load_dotenv, find_dotenv
from fastapi import HTTPException

load_dotenv(find_dotenv())

logger = logging.getLogger("gateway")


# Порождающий паттерн №1 singleton
# Гарантирует единственный экземпляр конфигурации шлюза в памяти
class GatewayConfigSingleton:
    _instance: Optional["GatewayConfigSingleton"] = None

    def __new__(cls) -> "GatewayConfigSingleton":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.service_urls = {
                "users-service": os.getenv("USERS_SERVICE_URL", "http://localhost:8001"),
                "catalog-service": os.getenv("CATALOG_SERVICE_URL", "http://localhost:8002"),
                "request-service": os.getenv("REQUEST_SERVICE_URL", "http://localhost:8003"),
                "locker-service": os.getenv("LOCKER_SERVICE_URL", "http://localhost:8004"),
                "stats-service": os.getenv("STATS_SERVICE_URL", "http://localhost:8005"),
            }
            cls._instance.use_mocks = os.getenv("USE_MOCKS", "true").lower() == "true"
            cls._instance.proxy_timeout = float(os.getenv("PROXY_TIMEOUT", "10"))
            cls._instance.cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
        return cls._instance


class AuthUser:
    def __init__(self, user_id: str, role: str):
        self.user_id = user_id
        self.role = role


# Порождающий паттерн №2 factory method
# Создает нужную реализацию клиента проверки токенов (Real HTTP или Mock)
class BaseAuthClient(ABC):
    @abstractmethod
    async def verify(self, token: str) -> AuthUser:
        pass


class RealUsersAuthClient(BaseAuthClient):
    def __init__(self, config: GatewayConfigSingleton, http: httpx.AsyncClient):
        self.config = config
        self.http = http

    async def verify(self, token: str) -> AuthUser:
        url = self.config.service_urls["users-service"] + "/internal/auth/verify"
        resp = await self.http.post(url, json={"token": token})
        if resp.status_code == 401 or resp.status_code == 403:
            raise HTTPException(status_code=401, detail="Недействительный или просроченный токен")
        if resp.status_code != 200:
            logger.error(f"Ошибка users-service при проверке токена: {resp.status_code}")
            raise HTTPException(status_code=502, detail="Ошибка users-service при проверке токена")

        data = resp.json()
        if "user_id" not in data or "role" not in data:
            logger.error(f"Некорректный ответ users-service на проверку токена: {data}")
            raise HTTPException(status_code=502, detail="Некорректный ответ users-service")
        return AuthUser(str(data["user_id"]), data["role"].upper())


class MockAuthClient(BaseAuthClient):
    MOCK_USERS = {
        "client": {"user_id": "USER0001", "role": "CLIENT"},
        "employee": {"user_id": "EMP00001", "role": "EMPLOYEE"},
        "manager": {"user_id": "MGR00001", "role": "MANAGER"},
        "admin": {"user_id": "ADM00001", "role": "ADMIN"},
    }

    async def verify(self, token: str) -> AuthUser:
        user = self.MOCK_USERS.get(token.lower())
        if user is None:
            raise HTTPException(status_code=401, detail="Недействительный или просроченный токен")
        return AuthUser(user["user_id"], user["role"])


class AuthClientFactory:
    @staticmethod
    def create_client(http: httpx.AsyncClient) -> BaseAuthClient:
        config = GatewayConfigSingleton()
        if config.use_mocks:
            return MockAuthClient()
        return RealUsersAuthClient(config, http)


# Структурный паттерн №1 proxy
# Контролирует доступ к users-service, логирует проверки токенов и обрабатывает 503
class LoggingAuthProxy(BaseAuthClient):
    def __init__(self, real_client: BaseAuthClient):
        self._wrapped = real_client

    async def verify(self, token: str) -> AuthUser:
        logger.info("Интеграция users-service -> POST /internal/auth/verify")
        try:
            user = await self._wrapped.verify(token)
        except httpx.RequestError as exc:
            logger.error(f"users-service недоступен: {exc}")
            raise HTTPException(status_code=503, detail="users-service временно недоступен")
        except HTTPException as exc:
            if exc.status_code == 401:
                logger.warning("Отклонён запрос: недействительный токен")
            raise

        logger.info(f"Ответ users-service <- 200 OK: пользователь {user.user_id}, роль {user.role}")
        return user
