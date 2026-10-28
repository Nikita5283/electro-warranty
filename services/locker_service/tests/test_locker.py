import os
import sys
import tempfile

# Отдельная временная БД для тестов, до импорта приложения
DB_FILE = os.path.join(tempfile.mkdtemp(), "lockers_test.db")
os.environ["LOCKERS_DB_URL"] = f"sqlite:///{DB_FILE}"
os.environ["SEED_CELLS"] = "A-101,A-102"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "locker-service"


def test_seed_and_filter(client):
    codes = [cell["code"] for cell in client.get("/api/v1/cells?status=FREE").json()]
    assert codes == ["A-101", "A-102"]
    assert client.get("/api/v1/cells?status=WRONG").status_code == 422


def test_occupy_and_release(client):
    resp = client.post("/internal/cells/A-101/occupy", json={"request_id": "REQ00001"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "OCCUPIED"
    assert resp.json()["request_id"] == "REQ00001"

    # Та же заявка повторно - не ошибка
    assert client.post("/internal/cells/A-101/occupy", json={"request_id": "REQ00001"}).status_code == 200
    # Другая заявка - ячейка занята
    assert client.post("/internal/cells/A-101/occupy", json={"request_id": "REQ00002"}).status_code == 409
    assert client.post("/internal/cells/A-101/release", json={"request_id": "REQ00002"}).status_code == 409

    free_codes = [cell["code"] for cell in client.get("/api/v1/cells?status=FREE").json()]
    assert free_codes == ["A-102"]

    resp = client.post("/internal/cells/A-101/release", json={"request_id": "REQ00001"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "FREE"
    assert resp.json()["request_id"] is None
    # Повторное освобождение - не ошибка
    assert client.post("/internal/cells/A-101/release", json={"request_id": "REQ00001"}).status_code == 200

    # После освобождения ячейку может занять другая заявка
    assert client.post("/internal/cells/A-101/occupy", json={"request_id": "REQ00002"}).status_code == 200


def test_unknown_cell(client):
    assert client.post("/internal/cells/Z-999/occupy", json={"request_id": "REQ00001"}).status_code == 404


def test_create_cell(client):
    resp = client.post("/api/v1/cells", json={"code": "C-301"}, headers={"X-User-Id": "ADM00001"})
    assert resp.status_code == 201
    assert resp.json()["status"] == "FREE"
    assert client.post("/api/v1/cells", json={"code": "C-301"}).status_code == 409


def test_history_and_audit(client):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from database import engine
    from models import CellAssignmentModel, AuditLogModel

    with Session(engine) as db:
        assignments = db.scalars(select(CellAssignmentModel)).all()
        actions = [row.action for row in db.scalars(select(AuditLogModel)).all()]
    # REQ00001 закрыто, REQ00002 открыто
    assert len(assignments) == 2
    assert sum(1 for a in assignments if a.released_at is None) == 1
    assert actions.count("create") == 3
    assert actions.count("occupy") == 2
    assert actions.count("release") == 1
