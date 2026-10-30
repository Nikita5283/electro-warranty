import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from fastapi import HTTPException, Request, Response

from clients import (
    AuthUser,
    BaseAuthClient,
    AuthClientFactory,
    LoggingAuthProxy,
    GatewayConfigSingleton,
)
from routes import RouteRule, find_route, ADMIN, CLIENT

logger = logging.getLogger("gateway")

SKIP_REQUEST_HEADERS = [
    "host", "content-length", "connection", "authorization", "x-user-id", "x-user-role",
]
SKIP_RESPONSE_HEADERS = [
    "content-length", "content-encoding", "transfer-encoding", "connection",
]


class GatewayContext:
    def __init__(self, request: Request):
        self.request = request
        self.method = request.method
        self.path = request.url.path
        self.rule: Optional[RouteRule] = None
        self.user: Optional[AuthUser] = None


# Поведенческий паттерн №1 chain of responsibility (Цепочка обязанностей)
# Последовательная обработка запроса: закрытые пути -> маршрут -> токен -> роль
class GatewayHandler(ABC):
    def __init__(self, next_handler: Optional["GatewayHandler"] = None):
        self._next = next_handler

    async def handle(self, ctx: GatewayContext) -> None:
        await self._process(ctx)
        if self._next:
            await self._next.handle(ctx)

    @abstractmethod
    async def _process(self, ctx: GatewayContext) -> None:
        pass


class InternalPathHandler(GatewayHandler):
    """Звено 1 Внутренние методы /internal наружу не публикуются"""
    async def _process(self, ctx: GatewayContext) -> None:
        if ctx.path.startswith("/internal"):
            logger.warning(f"Отклонён запрос к внутреннему методу: {ctx.method} {ctx.path}")
            raise HTTPException(status_code=404, detail="Метод не найден")


class RouteResolveHandler(GatewayHandler):
    """Звено 2 Поиск сервиса по таблице маршрутов"""
    async def _process(self, ctx: GatewayContext) -> None:
        rule, path_found = find_route(ctx.method, ctx.path)
        if rule is None and path_found:
            raise HTTPException(status_code=405, detail="Метод не поддерживается для этого пути")
        if rule is None:
            raise HTTPException(status_code=404, detail="Метод не найден")
        ctx.rule = rule


class AuthenticationHandler(GatewayHandler):
    """Звено 3 Проверка JWT-токена в users-service (кроме публичных методов)"""
    def __init__(self, auth_client: BaseAuthClient, next_handler: Optional[GatewayHandler] = None):
        super().__init__(next_handler)
        self.auth_client = auth_client

    async def _process(self, ctx: GatewayContext) -> None:
        if ctx.rule.roles is None:
            return
        header = ctx.request.headers.get("Authorization", "")
        token = header[len("Bearer "):].strip()
        if not header.lower().startswith("bearer ") or token == "":
            logger.warning(f"Отклонён запрос без токена: {ctx.method} {ctx.path}")
            raise HTTPException(
                status_code=401,
                detail="Требуется авторизация (заголовок Authorization: Bearer <token>)",
            )
        ctx.user = await self.auth_client.verify(token)


class RoleHandler(GatewayHandler):
    """Звено 4 Проверка роли пользователя для метода"""
    async def _process(self, ctx: GatewayContext) -> None:
        if ctx.rule.roles is None or ctx.user.role == ADMIN:
            return
        if ctx.user.role not in ctx.rule.roles:
            logger.warning(
                f"Отклонён запрос: роль {ctx.user.role} (пользователь {ctx.user.user_id}) "
                f"не имеет доступа к {ctx.method} {ctx.path}"
            )
            raise HTTPException(status_code=403, detail="Недостаточно прав для выполнения операции")


# Структурный паттерн №2 facade
# Единая точка входа: проверка запроса цепочкой и проксирование в нужный сервис
class GatewayFacade:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.config = GatewayConfigSingleton()
        auth_client = LoggingAuthProxy(AuthClientFactory.create_client(http))

        role_handler = RoleHandler()
        auth_handler = AuthenticationHandler(auth_client, role_handler)
        route_handler = RouteResolveHandler(auth_handler)
        self.chain = InternalPathHandler(route_handler)

    async def handle(self, request: Request) -> Response:
        ctx = GatewayContext(request)
        await self.chain.handle(ctx)
        return await self._forward(ctx)

    def _build_headers(self, ctx: GatewayContext) -> dict:
        headers = {}
        for name, value in ctx.request.headers.items():
            if name.lower() not in SKIP_REQUEST_HEADERS:
                headers[name] = value
        if ctx.user:
            headers["X-User-Id"] = ctx.user.user_id
            headers["X-User-Role"] = ctx.user.role
        return headers

    def _build_params(self, ctx: GatewayContext) -> dict:
        params = dict(ctx.request.query_params)
        if ctx.rule.scope_to_client and ctx.user and ctx.user.role == CLIENT:
            params["client_id"] = ctx.user.user_id
        return params

    async def _forward(self, ctx: GatewayContext) -> Response:
        service = ctx.rule.service
        url = self.config.service_urls[service] + ctx.path
        logger.info(f"Маршрутизация {ctx.method} {ctx.path} -> {service}")
        try:
            resp = await self.http.request(
                ctx.method,
                url,
                params=self._build_params(ctx),
                headers=self._build_headers(ctx),
                content=await ctx.request.body(),
            )
        except httpx.TimeoutException:
            logger.error(f"{service} не ответил за {self.config.proxy_timeout} с: {ctx.method} {ctx.path}")
            raise HTTPException(status_code=504, detail=f"{service} не ответил вовремя")
        except httpx.RequestError as exc:
            logger.error(f"{service} недоступен: {exc}")
            raise HTTPException(status_code=503, detail=f"{service} временно недоступен")

        logger.info(f"Ответ {service} <- {resp.status_code} для {ctx.method} {ctx.path}")
        headers = {}
        for name, value in resp.headers.items():
            if name.lower() not in SKIP_RESPONSE_HEADERS:
                headers[name] = value
        return Response(content=resp.content, status_code=resp.status_code, headers=headers)

    async def _check_service(self, base_url: str) -> str:
        try:
            resp = await self.http.get(base_url + "/health", timeout=httpx.Timeout(1.0, connect=0.5))
        except (httpx.RequestError, Exception):
            return "unavailable"
        if resp.status_code == 200:
            return "ok"
        return "unavailable"

    async def services_health(self) -> dict:
        names = list(self.config.service_urls.keys())
        checks = [self._check_service(self.config.service_urls[name]) for name in names]
        results = await asyncio.gather(*checks)

        health = {}
        for name, result in zip(names, results):
            health[name] = result
        return health
