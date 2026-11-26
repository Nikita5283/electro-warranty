import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))


@pytest.fixture(scope="module")
def client():
    original_modules = sys.modules.copy()
    db_test_path = SERVICE_DIR / "test_requests.db"
    if db_test_path.exists():
        db_test_path.unlink()

    os.environ["REQUESTS_DB_URL"] = f"sqlite:///{db_test_path.as_posix()}"

    from main import app
    with TestClient(app) as test_client:
        yield test_client

    if db_test_path.exists():
        try:
            db_test_path.unlink()
        except Exception:
            pass

    for k in list(sys.modules.keys()):
        if k not in original_modules and ("models" in k or "database" in k or "patterns" in k):
            del sys.modules[k]


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "stats-service"


def test_stats_requests_json(client):
    response = client.get("/api/v1/stats/requests")
    assert response.status_code == 200
    data = response.json()
    assert "total_requests" in data
    assert "by_status" in data
    assert "avg_duration_days" in data
    assert "requests" in data
    assert isinstance(data["requests"], list)
    assert data["total_requests"] >= 1


def test_stats_requests_csv(client):
    response = client.get("/api/v1/stats/requests?format=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    content = response.text
    # Проверяем наличие заголовков по Таблице 3 ПР
    assert "№ заявки;Дата создания;Товар;Сотрудник;Статус;Дата закрытия" in content


def test_stats_employees_json(client):
    response = client.get("/api/v1/stats/employees")
    assert response.status_code == 200
    data = response.json()
    assert "total_employees" in data
    assert "employees" in data
    assert len(data["employees"]) >= 1
    emp = data["employees"][0]
    assert "full_name" in emp
    assert "completed_count" in emp
    assert "avg_time_days" in emp


def test_stats_employees_csv(client):
    response = client.get("/api/v1/stats/employees?format=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    content = response.text
    # Проверяем наличие заголовков по Таблице 4 ПР
    assert "ФИО сотрудника;Обработано заявок;Среднее время обработки, дн." in content


def test_stats_products_json(client):
    response = client.get("/api/v1/stats/products")
    assert response.status_code == 200
    data = response.json()
    assert "total_claims" in data
    assert "products" in data
    prods = data["products"]
    assert len(prods) >= 1
    # Проверяем сортировку по убыванию количества заявок
    counts = [p["requests_count"] for p in prods]
    assert counts == sorted(counts, reverse=True)


def test_stats_products_csv(client):
    response = client.get("/api/v1/stats/products?format=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    content = response.text
    # Проверяем наличие заголовков по Таблице 5 ПР
    assert "Товар;Категория;Количество заявок" in content
