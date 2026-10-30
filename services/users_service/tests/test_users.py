import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient

# Отдельная временная БД для тестов
DB_FILE = os.path.join(tempfile.mkdtemp(), "users_test.db")
os.environ["USERS_DB_URL"] = f"sqlite:///{DB_FILE}"

users_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def client():
    # Сохраняем и восстанавливаем sys.modules для чистой изоляции при запуске из корня
    prev_sys_path = list(sys.path)
    if users_dir not in sys.path:
        sys.path.insert(0, users_dir)

    prev_modules = {k: sys.modules.get(k) for k in ["main", "database", "models", "patterns", "schemas", "routers"]}
    for mod in ["main", "database", "models", "patterns", "schemas", "routers"]:
        sys.modules.pop(mod, None)

    import main as users_main

    with TestClient(users_main.app) as test_client:
        yield test_client

    # Восстановление
    for k, v in prev_modules.items():
        if v is not None:
            sys.modules[k] = v
        else:
            sys.modules.pop(k, None)
    sys.path[:] = prev_sys_path


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "users-service"
    assert resp.json()["status"] == "ok"


def test_seed_users(client):
    resp = client.get("/api/v1/users/USER0001")
    assert resp.status_code == 200
    assert resp.json()["role"] == "CLIENT"
    assert resp.json()["email"] == "client@example.com"

    resp_emp = client.get("/api/v1/users/EMP00001")
    assert resp_emp.status_code == 200
    assert resp_emp.json()["role"] == "EMPLOYEE"


def test_register_and_login(client):
    # Успешная регистрация
    reg_payload = {
        "email": "newuser@example.com",
        "password": "strongpassword123",
        "full_name": "Новый Пользователь",
        "phone": "+79998887766",
        "role": "CLIENT",
    }
    resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "newuser@example.com"
    user_id = data["user"]["id"]

    # Повторная регистрация с тем же email - конфликт 409
    resp_dup = client.post("/api/v1/auth/register", json=reg_payload)
    assert resp_dup.status_code == 409

    # Вход с верными данными
    login_resp = client.post("/api/v1/auth/login", json={"email": "newuser@example.com", "password": "strongpassword123"})
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    token = login_data["access_token"]
    assert token

    # Вход с неверным паролем
    wrong_pwd = client.post("/api/v1/auth/login", json={"email": "newuser@example.com", "password": "wrongpassword"})
    assert wrong_pwd.status_code == 401

    # Вход несуществующего пользователя
    wrong_user = client.post("/api/v1/auth/login", json={"email": "notfound@example.com", "password": "password"})
    assert wrong_user.status_code == 401

    # Проверка JWT-токена через internal endpoint
    verify_resp = client.post("/internal/auth/verify", json={"token": token})
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["user_id"] == user_id
    assert verify_data["role"] == "CLIENT"


def test_verify_mock_tokens(client):
    for role_name, expected_id, expected_role in [
        ("client", "USER0001", "CLIENT"),
        ("employee", "EMP00001", "EMPLOYEE"),
        ("manager", "MGR00001", "MANAGER"),
        ("admin", "ADM00001", "ADMIN"),
    ]:
        resp = client.post("/internal/auth/verify", json={"token": role_name})
        assert resp.status_code == 200
        assert resp.json()["user_id"] == expected_id
        assert resp.json()["role"] == expected_role

    # Недействительный токен
    assert client.post("/internal/auth/verify", json={"token": "invalid.jwt.token"}).status_code == 401


def test_users_api_and_internal(client):
    # Получение по ID
    resp = client.get("/api/v1/users/EMP00001")
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Петров Пётр Сергеевич"

    # Несуществующий пользователь
    assert client.get("/api/v1/users/NONEXIST").status_code == 404

    # Internal users endpoint для stats-service
    resp_int = client.get("/internal/users/EMP00001")
    assert resp_int.status_code == 200
    assert resp_int.json()["full_name"] == "Петров Пётр Сергеевич"
    assert resp_int.json()["role"] == "EMPLOYEE"

    # Список пользователей с фильтром по роли
    resp_list = client.get("/api/v1/users?role=EMPLOYEE")
    assert resp_list.status_code == 200
    assert all(u["role"] == "EMPLOYEE" for u in resp_list.json())
