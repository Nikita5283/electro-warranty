import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Добавляем каталог сервиса в sys.path
SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))


@pytest.fixture(scope="module")
def client():
    # Сохраняем исходные модули для изоляции тестов
    original_modules = sys.modules.copy()
    db_test_path = SERVICE_DIR / "test_catalog.db"
    if db_test_path.exists():
        db_test_path.unlink()

    os.environ["CATALOG_DB_URL"] = f"sqlite:///{db_test_path.as_posix()}"
    os.environ["SEED_CATALOG"] = "true"

    from main import app
    with TestClient(app) as test_client:
        yield test_client

    if db_test_path.exists():
        try:
            db_test_path.unlink()
        except Exception:
            pass

    # Восстанавливаем sys.modules
    for k in list(sys.modules.keys()):
        if k not in original_modules and ("models" in k or "database" in k or "patterns" in k):
            del sys.modules[k]


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "catalog-service"


def test_list_products(client):
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 6
    names = [p["name"] for p in products]
    assert any("Galaxy S24" in name for name in names)


def test_get_product_by_id(client):
    response = client.get("/api/v1/products/PROD0001")
    assert response.status_code == 200
    prod = response.json()
    assert prod["id"] == "PROD0001"
    assert prod["category"] == "Смартфоны"
    assert prod["warranty_months"] == 24


def test_get_product_not_found(client):
    response = client.get("/api/v1/products/NONEXIST")
    assert response.status_code == 404


def test_create_and_update_product(client):
    # Создание нового товара
    create_resp = client.post(
        "/api/v1/products",
        json={
            "id": "PROD9999",
            "name": "Игровая приставка Station 5",
            "category": "Игры",
            "price": 54990.0,
            "warranty_months": 12,
        },
        headers={"X-User-Id": "ADM00001"},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["id"] == "PROD9999"

    # Обновление товара
    update_resp = client.put(
        "/api/v1/products/PROD9999",
        json={"price": 49990.0},
        headers={"X-User-Id": "ADM00001"},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["price"] == 49990.0


def test_buy_product(client):
    # Покупка товара клиентом USER0001
    resp = client.post(
        "/api/v1/purchases",
        json={"product_id": "PROD0001"},
        headers={"X-User-Id": "USER0001"},
    )
    assert resp.status_code == 201
    purchase = resp.json()
    assert purchase["product_id"] == "PROD0001"
    assert purchase["client_id"] == "USER0001"
    assert purchase["serial_number"].startswith("SN-PHN-")
    assert purchase["is_warranty_valid"] is True


def test_get_purchases_without_client_id_fails(client):
    resp = client.post("/api/v1/purchases", json={"product_id": "PROD0001"})
    assert resp.status_code == 400


def test_list_client_purchases(client):
    resp = client.get("/api/v1/purchases", headers={"X-User-Id": "USER0001"})
    assert resp.status_code == 200
    purchases = resp.json()
    assert len(purchases) >= 3
    # Проверяем, что в списке есть и действующие, и просроченные гарантии
    has_valid = any(p["is_warranty_valid"] for p in purchases)
    has_expired = any(not p["is_warranty_valid"] for p in purchases)
    assert has_valid and has_expired


def test_internal_purchase_for_requests(client):
    resp = client.get("/internal/purchases/PUR00001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["client_id"] == "USER0001"
    assert data["product_id"] == "PROD0001"
    assert "warranty_until" in data
    assert "product_name" in data


def test_internal_product_for_stats(client):
    resp = client.get("/internal/products/PROD0001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "PROD0001"
    assert data["name"] == "Смартфон Galaxy S24 Ultra"
    assert data["category"] == "Смартфоны"
