# Система гарантийного обслуживания электротоваров

Учебный микросервисный проект. Система ведёт покупателя от покупки товара в магазине до получения обслуженного товара из ячейки постамата. Работа идёт через три веб-кабинета: клиента, сотрудника сервиса и руководителя.

## Сервисы

| Сервис | Порт | Назначение | Статус |
|---|---|---|---|
| [gateway](services/gateway_service/README.md) | 8000 | Единая точка входа: проверка токена и роли, маршрутизация | готов |
| [users-service](services/users_service/README.md) | 8001 | Регистрация, вход, JWT, пользователи и роли | готов |
| catalog-service | 8002 | Каталог товаров, покупки, срок гарантии | в разработке |
| [request-service](services/request_service/README.md) | 8003 | Гарантийные заявки и история статусов | готов |
| [locker-service](services/locker_service/README.md) | 8004 | Ячейки постамата | готов |
| stats-service | 8005 | Статистика и отчёты для руководителя | в разработке |
| [panel](services/panel_service/README.md) | 9000 | Панель разработчика: схема проекта, статусы, ручки, таблицы | готов |

Все внешние запросы идут через gateway (`http://127.0.0.1:8000`). Методы `/internal/*` используются только для общения сервисов между собой.

## Структура

```
services/
  gateway_service/   API Gateway
  locker_service/    ячейки постамата
  panel_service/     панель разработчика
  request_service/   сервис заявок
  users_service/     пользователи и аутентификация
requirements.txt     общие зависимости
```

## Быстрый старт

1. Создать виртуальное окружение и установить зависимости [request-service](services/request_service/README.md).
2. Запустить нужные сервисы, каждый в своём терминале, на своём порту.
3. Отправлять запросы на gateway (порт 8000) или смотреть всё в панели (порт 9000).

## Запуск всей системы

Все сервисы упакованы в Docker и запускаются одной командой:

```bash
docker compose up --build
```

Запуск в фоновом режиме:

```bash
docker compose up --build -d
```

### Доступ к сервисам после запуска:

- **Панель разработчика:** [http://localhost:9000](http://localhost:9000)
- **API Gateway:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **Users Service (Swagger UI):** [http://localhost:8001/docs](http://localhost:8001/docs)
- **Request Service (Swagger UI):** [http://localhost:8003/docs](http://localhost:8003/docs)
- **Locker Service (Swagger UI):** [http://localhost:8004/docs](http://localhost:8004/docs)

### Остановка системы:

```bash
docker compose down
```

## Команда

- Жуков Михаил (ИТ-1-2024)
- Орлов Никита (ИТ-2-2024)
- Стариков Марат (ИТ-2-2024)
