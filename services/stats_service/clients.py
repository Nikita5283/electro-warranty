import os
import logging
from typing import Optional, Dict

import httpx
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

logger = logging.getLogger("stats-service")


# Порождающий паттерн №1: Singleton (Одиночка)
# Управляет сетевыми URL и параметрами взаимодействия со смежными микросервисами
class StatsConfigSingleton:
    _instance: Optional["StatsConfigSingleton"] = None

    def __new__(cls) -> "StatsConfigSingleton":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.users_service_url = os.getenv("USERS_SERVICE_URL", "http://127.0.0.1:8001")
            cls._instance.catalog_service_url = os.getenv("CATALOG_SERVICE_URL", "http://127.0.0.1:8002")
            cls._instance.http_timeout = float(os.getenv("EXTERNAL_TIMEOUT", "3.0"))
        return cls._instance


# Структурный паттерн №1: Adapter (Адаптер) + Caching
# Адаптирует получение метаданных из users-service и catalog-service с локальным кэшированием
class ExternalServiceAdapter:
    def __init__(self, http_client: Optional[httpx.Client] = None):
        self.config = StatsConfigSingleton()
        self.http = http_client or httpx.Client(timeout=self.config.http_timeout, trust_env=False)
        self._user_cache: Dict[str, str] = {}
        self._product_cache: Dict[str, Dict[str, str]] = {}

    def get_employee_name(self, employee_id: Optional[str]) -> str:
        """Получает ФИО сотрудника из users-service (GET /internal/users/{id})"""
        if not employee_id:
            return "Не назначен"
        if employee_id in self._user_cache:
            return self._user_cache[employee_id]

        url = f"{self.config.users_service_url}/internal/users/{employee_id}"
        try:
            resp = self.http.get(url)
            if resp.status_code == 200:
                data = resp.json()
                fio = data.get("full_name") or employee_id
                self._user_cache[employee_id] = fio
                return fio
        except Exception as exc:
            logger.warning(f"Не удалось получить ФИО сотрудника {employee_id} из users-service: {exc}")

        # Fallback к известным демо-сотрудникам или идентификатору
        fallback_names = {
            "EMP00001": "Петров Пётр Петрович",
            "MGR00001": "Ольга Менеджер",
            "ADM00001": "Игорь Администратор",
        }
        name = fallback_names.get(employee_id, employee_id)
        self._user_cache[employee_id] = name
        return name

    def get_product_info(self, product_id: Optional[str]) -> Dict[str, str]:
        """Получает наименование и категорию товара из catalog-service (GET /internal/products/{id})"""
        if not product_id:
            return {"name": "Неизвестный товар", "category": "Без категории"}
        if product_id in self._product_cache:
            return self._product_cache[product_id]

        url = f"{self.config.catalog_service_url}/internal/products/{product_id}"
        try:
            resp = self.http.get(url)
            if resp.status_code == 200:
                data = resp.json()
                info = {
                    "name": data.get("name", product_id),
                    "category": data.get("category", "Электроника"),
                }
                self._product_cache[product_id] = info
                return info
        except Exception as exc:
            logger.warning(f"Не удалось получить данные товара {product_id} из catalog-service: {exc}")

        fallback_products = {
            "PROD0001": {"name": "Смартфон Galaxy S24 Ultra", "category": "Смартфоны"},
            "PROD0002": {"name": "Ноутбук ThinkPad X1 Carbon Gen 11", "category": "Ноутбуки"},
            "PROD0003": {"name": "Телевизор OLED Smart TV 55", "category": "Телевизоры"},
            "PROD0004": {"name": "Беспроводные наушники WH-1000XM5", "category": "Аудио"},
            "PROD0005": {"name": "Робот-пылесос RoboVac X8 Pro", "category": "Бытовая техника"},
            "PROD0006": {"name": "Кофемашина Barista Touch", "category": "Бытовая техника"},
        }
        info = fallback_products.get(product_id, {"name": product_id, "category": "Электротовары"})
        self._product_cache[product_id] = info
        return info
