## API Gateway

Единая точка входа системы. Проверяет JWT-токен и роль, затем пересылает запрос в нужный сервис с заголовками `X-User-Id` и `X-User-Role`. Методы `/internal/*` снаружи недоступны.

Коды ошибок: 401 - нет или неверный токен, 403 - нет прав, 404/405 - неизвестный путь или метод, 503/504 - сервис недоступен или не ответил.

### Запуск

```bash
cd services/gateway_service
uvicorn main:app --reload --port 8000
```

Состояние шлюза и сервисов: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### Переменные окружения

| Переменная | По умолчанию |
|---|---|
| `USERS_SERVICE_URL` ... `STATS_SERVICE_URL` | `http://localhost:8001` ... `8005` |
| `USE_MOCKS` | `true` |
| `PROXY_TIMEOUT` | `10` |
| `CORS_ORIGINS` | `*` |

### Заглушки (`USE_MOCKS=true`)

Пока нет users-service, токен - это имя роли: `Authorization: Bearer client`.

| Токен | X-User-Id | Роль |
|---|---|---|
| `client` | `USER0001` | `CLIENT` |
| `employee` | `EMP00001` | `EMPLOYEE` |
| `manager` | `MGR00001` | `MANAGER` |
| `admin` | `ADM00001` | `ADMIN` |

### Контракт с users-service

```
POST /internal/auth/verify  {"token": "<jwt>"}
200 {"user_id": "USER0001", "role": "CLIENT"} | 401
```

### Маршруты и права

Таблица `ROUTES` в `routes.py`. `ADMIN` имеет доступ ко всем методам.

### Паттерны

* **Singleton** - `GatewayConfigSingleton`
* **Factory Method** - `AuthClientFactory`
* **Proxy** - `LoggingAuthProxy`
* **Chain of Responsibility** - `InternalPathHandler` -> `RouteResolveHandler` -> `AuthenticationHandler` -> `RoleHandler`
* **Facade** - `GatewayFacade`
