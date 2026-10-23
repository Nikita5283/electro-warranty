import os
import time
import asyncio
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv, find_dotenv

from topology import SERVICES, DATABASES

load_dotenv(find_dotenv())

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Порождающий паттерн №1 singleton
# Гарантирует единственный экземпляр конфигурации панели в памяти
class PanelConfigSingleton:
    _instance: Optional["PanelConfigSingleton"] = None

    def __new__(cls) -> "PanelConfigSingleton":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.service_urls = {}
            for service in SERVICES:
                default_url = f"http://127.0.0.1:{service['port']}"
                cls._instance.service_urls[service["id"]] = os.getenv(service["env"], default_url)

            cls._instance.database_urls = {}
            for db in DATABASES:
                default_url = "sqlite:///" + str(PROJECT_ROOT / db["default_file"])
                cls._instance.database_urls[db["id"]] = os.getenv(db["env"], default_url)
        return cls._instance


# Структурный паттерн №1 adapter
# Преобразует openapi.json сервиса в простой список ручек для панели
class OpenApiAdapter:
    def __init__(self, openapi: dict):
        self.openapi = openapi

    def to_endpoints(self) -> list:
        endpoints = []
        for path, methods in self.openapi.get("paths", {}).items():
            for method, info in methods.items():
                if method.upper() not in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                    continue
                endpoints.append({
                    "method": method.upper(),
                    "path": path,
                    "summary": info.get("summary", ""),
                    "description": info.get("description", ""),
                    "parameters": self._parameters(info),
                    "body_example": self._body_example(info),
                })
        return endpoints

    def _parameters(self, info: dict) -> list:
        result = []
        for param in info.get("parameters", []):
            if "$ref" in param:
                continue
            schema = param.get("schema", {})
            result.append({
                "name": param.get("name"),
                "in": param.get("in"),
                "required": param.get("required", False),
                "default": schema.get("default"),
                "description": param.get("description", ""),
            })
        return result

    def _body_example(self, info: dict):
        content = info.get("requestBody", {}).get("content", {})
        schema = content.get("application/json", {}).get("schema")
        if not schema:
            return None
        return self._example_from_schema(schema, 0)

    def _resolve(self, schema: dict) -> dict:
        if "$ref" in schema:
            name = schema["$ref"].split("/")[-1]
            return self.openapi.get("components", {}).get("schemas", {}).get(name, {})
        if "anyOf" in schema:
            for option in schema["anyOf"]:
                if option.get("type") != "null":
                    return self._resolve(option)
        return schema

    def _example_from_schema(self, schema: dict, depth: int):
        schema = self._resolve(schema)
        if depth > 4:
            return None
        if "default" in schema:
            return schema["default"]
        schema_type = schema.get("type")
        if schema_type == "object" or "properties" in schema:
            example = {}
            for name, prop in schema.get("properties", {}).items():
                example[name] = self._example_from_schema(prop, depth + 1)
            return example
        if schema_type == "array":
            return [self._example_from_schema(schema.get("items", {}), depth + 1)]
        if schema_type == "integer":
            return 0
        if schema_type == "number":
            return 0.0
        if schema_type == "boolean":
            return False
        if schema_type == "string":
            return ""
        return None


class ServiceClient:
    def __init__(self, http: httpx.AsyncClient):
        # Отключаем системный прокси для локальных межсервисных вызовов 127.0.0.1
        self.http = http if not getattr(http, "trust_env", True) else httpx.AsyncClient(trust_env=False)
        self.config = PanelConfigSingleton()

    async def check_service(self, service_id: str) -> dict:
        url = self.config.service_urls[service_id]
        start = time.perf_counter()
        try:
            resp = await self.http.get(url + "/health", timeout=4.0)
        except httpx.TimeoutException:
            return {"id": service_id, "url": url, "online": True, "status": "timeout", "latency_ms": None, "health": None}
        except httpx.RequestError:
            return {"id": service_id, "url": url, "online": False, "status": "offline", "latency_ms": None, "health": None}

        latency = round((time.perf_counter() - start) * 1000)
        try:
            health = resp.json()
        except ValueError:
            health = None
        status = "online" if resp.status_code == 200 else "error"
        return {"id": service_id, "url": url, "online": True, "status": status, "latency_ms": latency, "health": health}

    async def check_all(self) -> list:
        checks = [self.check_service(service["id"]) for service in SERVICES]
        return await asyncio.gather(*checks)

    async def get_openapi(self, service_id: str) -> Optional[dict]:
        url = self.config.service_urls[service_id]
        try:
            resp = await self.http.get(url + "/openapi.json", timeout=3.0)
        except httpx.RequestError:
            return None
        if resp.status_code != 200:
            return None
        return resp.json()

    async def send(self, service_id: str, method: str, path: str, query: dict, headers: dict, body: Optional[str]) -> dict:
        url = self.config.service_urls[service_id] + path
        start = time.perf_counter()
        try:
            resp = await self.http.request(
                method,
                url,
                params=query,
                headers=headers,
                content=body.encode("utf-8") if body else None,
                timeout=15.0,
            )
        except httpx.TimeoutException:
            return {"ok": False, "error": "Сервис не ответил за 15 секунд"}
        except httpx.RequestError as exc:
            return {"ok": False, "error": f"Сервис недоступен: {exc}"}

        elapsed = round((time.perf_counter() - start) * 1000)
        return {
            "ok": True,
            "status": resp.status_code,
            "elapsed_ms": elapsed,
            "headers": dict(resp.headers),
            "body": resp.text,
            "url": str(resp.request.url),
        }
