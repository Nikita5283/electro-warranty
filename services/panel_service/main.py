import asyncio
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.engine import make_url

from clients import PanelConfigSingleton, ServiceClient, OpenApiAdapter, PROJECT_ROOT
from db_reader import DatabaseReaderFactory
from patterns_info import PATTERNS
from topology import SERVICES, DATABASES, EDGES, MOCK_TOKENS


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(trust_env=False)
    app.state.readers = {}
    yield
    await app.state.http.aclose()


app = FastAPI(
    title="Control Panel",
    description="Панель управления проектом electro-warranty",
    version="1.0.0",
    lifespan=lifespan,
)


class SendRequestSchema(BaseModel):
    method: str
    path: str
    query: dict = {}
    headers: dict = {}
    body: Optional[str] = None


def find_service(service_id: str) -> dict:
    for service in SERVICES:
        if service["id"] == service_id:
            return service
    raise HTTPException(status_code=404, detail="Сервис не найден")


def find_database(db_id: str) -> dict:
    for db in DATABASES:
        if db["id"] == db_id:
            return db
    raise HTTPException(status_code=404, detail="База данных не найдена")


def get_reader(request: Request, db_id: str):
    url = PanelConfigSingleton().database_urls[db_id]
    if db_id not in request.app.state.readers:
        request.app.state.readers[db_id] = DatabaseReaderFactory.create_reader(url)
    return request.app.state.readers[db_id]


def safe_url(url: str) -> str:
    parsed = make_url(url)
    if parsed.drivername.startswith("sqlite"):
        path = Path(parsed.database)
        if path.is_relative_to(PROJECT_ROOT):
            return "sqlite:///" + path.relative_to(PROJECT_ROOT).as_posix()
        return "sqlite:///" + path.as_posix()
    return parsed.render_as_string(hide_password=True)


def normalize_path(path: str) -> str:
    return re.sub(r"\{[^/]+\}", "{}", path)


def database_status(request: Request, db_id: str) -> dict:
    reader = get_reader(request, db_id)
    if not reader.exists():
        return {"id": db_id, "online": False, "tables": 0, "rows": 0}
    try:
        tables = reader.tables()
    except Exception as exc:
        return {"id": db_id, "online": False, "tables": 0, "rows": 0, "error": str(exc)}
    rows = 0
    for table in tables:
        rows += table["rows"]
    return {"id": db_id, "online": True, "tables": len(tables), "rows": rows}


@app.get("/api/topology", tags=["Panel"])
def get_topology():
    config = PanelConfigSingleton()
    services = []
    for service in SERVICES:
        item = dict(service)
        item["url"] = config.service_urls[service["id"]]
        item["patterns"] = PATTERNS.get(service["id"], [])
        services.append(item)
    databases = []
    for db in DATABASES:
        item = dict(db)
        item["url"] = safe_url(config.database_urls[db["id"]])
        databases.append(item)
    return {"services": services, "databases": databases, "edges": EDGES, "mock_tokens": MOCK_TOKENS}


@app.get("/api/status", tags=["Panel"])
async def get_status(request: Request):
    client = ServiceClient(request.app.state.http)
    services = await client.check_all()
    databases = []
    for db in DATABASES:
        databases.append(await asyncio.to_thread(database_status, request, db["id"]))
    return {"services": services, "databases": databases, "checked_at": datetime.now().isoformat(timespec="seconds")}


@app.get("/api/services/{service_id}/endpoints", tags=["Panel"])
async def get_endpoints(service_id: str, request: Request):
    service = find_service(service_id)
    client = ServiceClient(request.app.state.http)
    openapi = await client.get_openapi(service_id)

    planned = service["endpoints"]
    if openapi is None:
        endpoints = []
        for endpoint in planned:
            item = dict(endpoint)
            item["state"] = "planned"
            endpoints.append(item)
        return {"source": "plan", "endpoints": endpoints}

    actual = OpenApiAdapter(openapi).to_endpoints()
    actual_keys = set()
    for endpoint in actual:
        actual_keys.add(endpoint["method"] + " " + normalize_path(endpoint["path"]))

    planned_info = {}
    for endpoint in planned:
        planned_info[endpoint["method"] + " " + normalize_path(endpoint["path"])] = endpoint

    endpoints = []
    for endpoint in actual:
        key = endpoint["method"] + " " + normalize_path(endpoint["path"])
        item = dict(endpoint)
        item["state"] = "implemented"
        if key in planned_info:
            item["roles"] = planned_info[key].get("roles")
            item["target"] = planned_info[key].get("target")
        endpoints.append(item)

    for key, endpoint in planned_info.items():
        if key in actual_keys:
            continue
        item = dict(endpoint)
        item["state"] = "proxy" if service_id == "gateway" else "planned"
        endpoints.append(item)

    return {"source": "openapi", "title": openapi.get("info", {}).get("title"), "endpoints": endpoints}


@app.post("/api/services/{service_id}/request", tags=["Panel"])
async def send_request(service_id: str, payload: SendRequestSchema, request: Request):
    find_service(service_id)
    client = ServiceClient(request.app.state.http)
    return await client.send(service_id, payload.method.upper(), payload.path, payload.query, payload.headers, payload.body)


@app.get("/api/databases/{db_id}/tables", tags=["Panel"])
def get_tables(db_id: str, request: Request):
    db = find_database(db_id)
    reader = get_reader(request, db_id)
    if not reader.exists():
        return {"online": False, "planned": db["tables"], "tables": []}
    try:
        return {"online": True, "planned": db["tables"], "tables": reader.tables()}
    except Exception as exc:
        return {"online": False, "planned": db["tables"], "tables": [], "error": str(exc)}


@app.get("/api/databases/{db_id}/tables/{table_name}", tags=["Panel"])
def get_rows(db_id: str, table_name: str, request: Request, search: str = "", limit: int = 50, offset: int = 0):
    find_database(db_id)
    reader = get_reader(request, db_id)
    if not reader.exists():
        raise HTTPException(status_code=404, detail="База данных ещё не создана")
    names = [table["name"] for table in reader.tables()]
    if table_name not in names:
        raise HTTPException(status_code=404, detail="Таблица не найдена")
    limit = max(1, min(limit, 200))
    return reader.rows(table_name, search.strip(), limit, max(0, offset))


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
