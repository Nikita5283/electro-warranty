from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from patterns import CatalogServiceFacade
from schemas import (
    ProductOut,
    ProductCreateSchema,
    ProductUpdateSchema,
    PurchaseOut,
    PurchaseCreateSchema,
    InternalPurchaseOut,
    InternalProductOut,
)

products_router = APIRouter(prefix="/api/v1/products", tags=["Products"])
purchases_router = APIRouter(prefix="/api/v1/purchases", tags=["Purchases"])
internal_router = APIRouter(prefix="/internal", tags=["Internal"])


# Каталог товаров (/api/v1/products)

@products_router.get("", response_model=List[ProductOut])
def get_products(
    category: Optional[str] = Query(None, description="Фильтр по категории"),
    search: Optional[str] = Query(None, description="Поиск по наименованию"),
    db: Session = Depends(get_db),
):
    """Каталог товаров магазина электротоваров с возможностью поиска и фильтрации"""
    facade = CatalogServiceFacade(db)
    return facade.list_products(category=category, search=search)


@products_router.get("/{id}", response_model=ProductOut)
def get_product_by_id(id: str, db: Session = Depends(get_db)):
    """Получение детальной информации о товаре по идентификатору"""
    facade = CatalogServiceFacade(db)
    return facade.get_product(id)


@products_router.post("", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreateSchema,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    """Добавление нового товара в каталог (Администратор)"""
    facade = CatalogServiceFacade(db)
    return facade.create_product(payload, user_id=x_user_id)


@products_router.put("/{id}", response_model=ProductOut)
def update_product(
    id: str,
    payload: ProductUpdateSchema,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    """Обновление атрибутов товара в каталоге (Администратор)"""
    facade = CatalogServiceFacade(db)
    return facade.update_product(id, payload, user_id=x_user_id)


# Покупки клиентов (/api/v1/purchases)

@purchases_router.post("", response_model=PurchaseOut, status_code=201)
def buy_product(
    payload: PurchaseCreateSchema,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    client_id: Optional[str] = Query(None, description="ID клиента (если не передан в заголовке)"),
    db: Session = Depends(get_db),
):
    """Оформление покупки товара клиентом с фиксацией гарантийного срока"""
    resolved_client_id = x_user_id or client_id
    if not resolved_client_id:
        raise HTTPException(status_code=400, detail="Не указан идентификатор клиента (требуется X-User-Id)")

    facade = CatalogServiceFacade(db)
    purchase = facade.create_purchase(
        client_id=resolved_client_id,
        product_id=payload.product_id,
        serial_number=payload.serial_number,
    )
    return facade.get_purchase(purchase.id)


@purchases_router.get("", response_model=List[PurchaseOut])
def get_purchases(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    client_id: Optional[str] = Query(None, description="ID клиента для фильтрации"),
    db: Session = Depends(get_db),
):
    """Список покупок клиента с отображением статуса гарантии"""
    resolved_client_id = client_id or x_user_id
    if not resolved_client_id:
        raise HTTPException(status_code=400, detail="Не указан идентификатор клиента (требуется X-User-Id или client_id)")

    facade = CatalogServiceFacade(db)
    return facade.list_client_purchases(resolved_client_id)


@purchases_router.get("/{id}", response_model=PurchaseOut)
def get_purchase_by_id(id: str, db: Session = Depends(get_db)):
    """Карточка покупки с полной информацией о товаре и гарантии"""
    facade = CatalogServiceFacade(db)
    return facade.get_purchase(id)


# Межсервисные интерфейсы (/internal)

@internal_router.get("/purchases/{id}", response_model=InternalPurchaseOut)
def get_internal_purchase(id: str, db: Session = Depends(get_db)):
    """Межсервисный запрос данных покупки для request-service (проверка гарантии при создании заявки)"""
    facade = CatalogServiceFacade(db)
    return facade.get_internal_purchase(id)


@internal_router.get("/products/{id}", response_model=InternalProductOut)
def get_internal_product(id: str, db: Session = Depends(get_db)):
    """Межсервисный запрос наименования товара для stats-service (отчёты по обращениям)"""
    facade = CatalogServiceFacade(db)
    return facade.get_internal_product(id)
