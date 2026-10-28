## Locker Service

Ведёт справочник ячеек постамата и их занятость. Сотрудник сервиса получает список свободных ячеек, request-service занимает ячейку при статусе "товар обслужен" и освобождает при выдаче товара.

### Запуск

```bash
cd services/locker_service
uvicorn main:app --reload --port 8004
```

* Swagger UI: [http://127.0.0.1:8004/docs](http://127.0.0.1:8004/docs)
* Проверка состояния: [http://127.0.0.1:8004/health](http://127.0.0.1:8004/health)

При первом запуске справочник заполняется ячейками `A-101` ... `A-105`, `B-201` ... `B-205`.

### Переменные окружения

| Переменная | По умолчанию |
|---|---|
| `LOCKERS_DB_URL` | `sqlite:///./lockers.db` |
| `SEED_CELLS` | `A-101,...,B-205` - коды через запятую для первого запуска |

### Методы

| Метод | Кто вызывает | Ответ |
|---|---|---|
| `GET /api/v1/cells?status=FREE` | сотрудник через gateway | список ячеек, `status` - `FREE` или `OCCUPIED` |
| `POST /api/v1/cells` `{"code"}` | администратор через gateway | 201, 409 если код уже есть |
| `POST /internal/cells/{code}/occupy` `{"request_id"}` | request-service | 200, 409 если занята другой заявкой, 404 если ячейки нет |
| `POST /internal/cells/{code}/release` `{"request_id"}` | request-service | 200, 409 если занята другой заявкой, 404 если ячейки нет |

Повторный occupy от той же заявки и повторный release свободной ячейки возвращают 200 без изменений.

### Данные

* `cell` - ячейка: код и статус.
* `cell_assignment` - назначение ячейки заявке: `assigned_at`, `released_at`.
* `audit_log` - протокол изменений справочника ячеек (создание, занятие, освобождение).

### Тесты

```bash
cd services/locker_service
python -m pytest tests
```

### Паттерны

* **Singleton** - `LockerConfigSingleton`
* **State** - `FreeState`, `OccupiedState`: что можно сделать с ячейкой в её статусе
* **Observer** - `CellAssignmentObserver`, `AuditLogDbObserver`, `FileLogObserver`
* **Facade** - `LockerServiceFacade`
