# Catalog Service

Микросервис управления каталогом товаров магазина электротоваров, оформления покупок клиентами, расчёта сроков гарантии и предоставления данных по покупкам и товарам для `request-service` и `stats-service`.

## Запуск сервиса локально:
```bash
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

---

## Архитектура и реализованные паттерны GoF

1. **Singleton** - `CatalogConfigSingleton` (`patterns.py`)
   Гарантирует единственный экземпляр конфигурации сервиса в памяти.
2. **Strategy (Стратегия)** — `WarrantyCalculatorStrategy` / `StandardCalendarWarrantyCalculator` (`patterns.py`):
   Инкапсулирует алгоритм календарного расчёта даты окончания гарантии на основе гарантийного срока производителя.
3. **Factory Method (Фабрика)** — `SerialNumberFactory` (`patterns.py`):
   Генерирует уникальные серийные номера изделий с префиксами по категориям электротоваров.
4. **Observer (Наблюдатель)** — `CatalogAuditObserver` (`patterns.py`):
   Протоколирует все добавления, изменения товаров и факты покупок в таблицу `audit_log` согласно разделу 9 Проектного решения (ПР).
5. **Facade (Фасад)** — `CatalogServiceFacade` (`patterns.py`):
   Предоставляет унифицированный высокоуровневый интерфейс ко всей бизнес-логике каталога и покупок.

---

## Структура базы данных (`catalog_db`)

- **`product`** — каталог товаров (`id`, `name`, `category`, `price`, `warranty_months`, `is_active`, `created_at`).
- **`purchase`** — покупки клиентов (`id`, `product_id`, `client_id`, `serial_number`, `purchase_date`, `warranty_until`).
- **`audit_log`** — аудит изменений справочников (`id`, `entity`, `entity_id`, `action`, `old_value`, `new_value`, `changed_by`, `changed_at`).

---

## Точки входа (API Endpoints)

### Публичные методы (через Gateway):
- `GET /health` — проверка работоспособности сервиса и доступности БД.
- `GET /api/v1/products` — список товаров с фильтрацией по категории и поиском.
- `GET /api/v1/products/{id}` — карточка товара.
- `POST /api/v1/products` — добавление товара (роль: `ADMIN`).
- `PUT /api/v1/products/{id}` — редактирование товара (роль: `ADMIN`).
- `POST /api/v1/purchases` — покупка товара клиентом (роль: `CLIENT`, заголовок `X-User-Id`).
- `GET /api/v1/purchases` — список покупок текущего клиента со статусом гарантии.
- `GET /api/v1/purchases/{id}` — детальная карточка покупки.

### Внутренние методы (`/internal`):
- `GET /internal/purchases/{id}` — проверка покупки для `request-service` (`client_id`, `product_id`, `warranty_until`, `product_name`).
- `GET /internal/products/{id}` — получение наименования и категории товара для `stats-service`.
