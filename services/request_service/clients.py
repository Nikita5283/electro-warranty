import os
import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional, Dict, Any

import httpx
from fastapi import HTTPException

logger = logging.getLogger("request-service")


# Порождающий паттерн №1 singleton
# Гарантирует единственный экземпляр конфигурации микросервиса в памяти
class ServiceConfigSingleton:
    _instance: Optional["ServiceConfigSingleton"] = None

    def __new__(cls) -> "ServiceConfigSingleton":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.catalog_url = os.getenv("CATALOG_SERVICE_URL", "http://localhost:8002")
            cls._instance.locker_url = os.getenv("LOCKER_SERVICE_URL", "http://localhost:8004")
            cls._instance.stats_url = os.getenv("STATS_SERVICE_URL", "http://localhost:8005")
            cls._instance.use_mocks = os.getenv("USE_MOCKS", "true").lower() == "true"
        return cls._instance


# Структурный паттерн №1 adapter
# Преобразует внешний JSON-ответ catalog-service во внутреннюю модель домена
class PurchaseDomainInfo:
    def __init__(self, client_id: str, product_id: str, warranty_until: date):
        self.client_id = client_id
        self.product_id = product_id
        self.warranty_until = warranty_until


class PurchaseDataAdapter:
    def __init__(self, raw_catalog_json: Dict[str, Any]):
        self.raw = raw_catalog_json

    def to_domain(self) -> PurchaseDomainInfo:
        try:
            warranty_date = date.fromisoformat(str(self.raw["warranty_until"])[:10])
            return PurchaseDomainInfo(
                client_id=str(self.raw["client_id"]),
                product_id=str(self.raw.get("product_id", "PROD0001")),
                warranty_until=warranty_date,
            )
        except (KeyError, ValueError) as exc:
            logger.error(f"Ошибка адаптации данных покупки от catalog-service: {exc}")
            raise HTTPException(status_code=500, detail="Некорректный формат данных от catalog-service")


# Порождающий паттерн №2 factory method
# Создает нужную реализацию сетевого клиента (Real HTTP или Mock)
class BaseExternalClient(ABC):
    @abstractmethod
    async def get_purchase(self, purchase_id: str) -> dict:
        pass

    @abstractmethod
    async def occupy_cell(self, cell_code: str, request_id: str) -> int:
        pass

    @abstractmethod
    async def release_cell(self, cell_code: str, request_id: str) -> int:
        pass

    @abstractmethod
    async def send_stats_event(self, payload: dict) -> None:
        pass


class RealHttpExternalClient(BaseExternalClient):
    """Боевой HTTP-клиент для взаимодействия с другими микросервисами через httpx"""
    def __init__(self, config: ServiceConfigSingleton):
        self.config = config

    async def get_purchase(self, purchase_id: str) -> dict:
        url = f"{self.config.catalog_url}/internal/purchases/{purchase_id}"
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                raise HTTPException(status_code=422, detail="Покупка не найдена в catalog-service")
            resp.raise_for_status()
            return resp.json()

    async def occupy_cell(self, cell_code: str, request_id: str) -> int:
        url = f"{self.config.locker_url}/internal/cells/{cell_code}/occupy"
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            resp = await client.post(url, json={"request_id": request_id})
            return resp.status_code

    async def release_cell(self, cell_code: str, request_id: str) -> int:
        url = f"{self.config.locker_url}/internal/cells/{cell_code}/release"
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            resp = await client.post(url, json={"request_id": request_id})
            return resp.status_code

    async def send_stats_event(self, payload: dict) -> None:
        request_id = payload.get("request_id")
        # По архплану отправляется только факт закрытия заявки, а stats-service читает общую БД
        url = f"{self.config.stats_url}/internal/requests/{request_id}/close"
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            try:
                resp = await client.post(url, json={"request_id": request_id})
                if resp.status_code == 404:
                    alt_url = f"{self.config.stats_url}/internal/events"
                    await client.post(alt_url, json={"request_id": request_id})
            except Exception as exc:
                logger.error(f"Не удалось отправить уведомление о закрытии в stats-service: {exc}")


class MockExternalClient(BaseExternalClient):
    """Имитационный клиент для тестирования всех сценариев без запуска соседних сервисов"""
    occupied_cells = {"CELL-BUSY"}

    async def get_purchase(self, purchase_id: str) -> dict:
        if purchase_id == "NOTFOUND":
            raise HTTPException(status_code=422, detail="Покупка не найдена в catalog-service")
        if purchase_id == "EXPIRED1":
            # Покупка с истекшей гарантией (для проверки кода 422)
            return {"id": purchase_id, "client_id": "USER0001", "product_id": "PROD0001", "warranty_until": "2020-01-01"}
        # Действующая гарантия для клиента USER0001
        return {"id": purchase_id, "client_id": "USER0001", "product_id": "PROD0001", "warranty_until": "2028-12-31"}

    async def occupy_cell(self, cell_code: str, request_id: str) -> int:
        if cell_code in self.occupied_cells:
            return 409  # Ячейка уже занята
        self.occupied_cells.add(cell_code)
        return 200

    async def release_cell(self, cell_code: str, request_id: str) -> int:
        self.occupied_cells.discard(cell_code)
        return 200

    async def send_stats_event(self, payload: dict) -> None:
        pass


class ExternalClientFactory:
    @staticmethod
    def create_client() -> BaseExternalClient:
        config = ServiceConfigSingleton()
        if config.use_mocks:
            return MockExternalClient()
        return RealHttpExternalClient(config)


# Структурный паттерн №2 proxy
# Контролирует доступ к внешним сервисам, логирует запросы и обрабатывает 503
class LoggingClientProxy(BaseExternalClient):
    def __init__(self, real_client: BaseExternalClient):
        self._wrapped = real_client

    async def get_purchase(self, purchase_id: str) -> dict:
        logger.info(f"Интеграция catalog-service -> GET /internal/purchases/{purchase_id}")
        try:
            data = await self._wrapped.get_purchase(purchase_id)
            logger.info(f"Ответ catalog-service <- 200 OK для покупки {purchase_id}")
            return data
        except httpx.RequestError as exc:
            logger.error(f"catalog-service недоступен: {exc}")
            raise HTTPException(status_code=503, detail="catalog-service временно недоступен")

    async def occupy_cell(self, cell_code: str, request_id: str) -> int:
        logger.info(f"Интеграция locker-service -> POST /internal/cells/{cell_code}/occupy (заявка {request_id})")
        try:
            status_code = await self._wrapped.occupy_cell(cell_code, request_id)
            if status_code == 409:
                logger.warning(f"Ответ locker-service <- 409 Conflict: ячейка {cell_code} уже занята")
            else:
                logger.info(f"Ответ locker-service <- {status_code} (ячейка {cell_code} занята)")
            return status_code
        except httpx.RequestError as exc:
            logger.error(f"locker-service недоступен: {exc}")
            raise HTTPException(status_code=503, detail="locker-service временно недоступен")

    async def release_cell(self, cell_code: str, request_id: str) -> int:
        logger.info(f"Интеграция locker-service -> POST /internal/cells/{cell_code}/release (заявка {request_id})")
        try:
            status_code = await self._wrapped.release_cell(cell_code, request_id)
            logger.info(f"Ответ locker-service <- {status_code} (ячейка {cell_code} освобождена)")
            return status_code
        except httpx.RequestError as exc:
            logger.error(f"locker-service недоступен: {exc}")
            raise HTTPException(status_code=503, detail="locker-service временно недоступен")

    async def send_stats_event(self, payload: dict) -> None:
        request_id = payload.get("request_id")
        logger.info(f"Интеграция stats-service -> факт закрытия заявки request_id={request_id}")
        try:
            await self._wrapped.send_stats_event(payload)
        except Exception as exc:
            logger.error(f"Не удалось отправить факт закрытия в stats-service: {exc}")
