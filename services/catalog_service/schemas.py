from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ProductCreateSchema(BaseModel):
    id: Optional[str] = Field(None, max_length=8, description="Пользовательский ID товара (опционально)")
    name: str = Field(..., max_length=500, description="Полное наименование товара")
    category: str = Field(..., max_length=100, description="Категория товара")
    price: float = Field(..., gt=0, description="Розничная цена товара")
    warranty_months: int = Field(..., gt=0, le=120, description="Срок гарантии производителя в месяцах")


class ProductUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    price: Optional[float] = Field(None, gt=0)
    warranty_months: Optional[int] = Field(None, gt=0, le=120)
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    id: str
    name: str
    category: str
    price: float
    warranty_months: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PurchaseCreateSchema(BaseModel):
    product_id: str = Field(..., max_length=8, description="Идентификатор приобретаемого товара")
    serial_number: Optional[str] = Field(None, max_length=50, description="Серийный номер изделия (генерируется автоматически, если не передан)")


class PurchaseOut(BaseModel):
    id: str
    product_id: str
    client_id: str
    serial_number: str
    purchase_date: datetime
    warranty_until: datetime
    is_warranty_valid: bool = False
    product_name: Optional[str] = None
    product_category: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InternalPurchaseOut(BaseModel):
    """Схема ответа для межсервисной интеграции с request-service (GET /internal/purchases/{id})"""
    id: str
    client_id: str
    product_id: str
    serial_number: str
    purchase_date: datetime
    warranty_until: datetime
    product_name: str

    model_config = ConfigDict(from_attributes=True)


class InternalProductOut(BaseModel):
    """Схема ответа для межсервисной интеграции со stats-service (GET /internal/products/{id})"""
    id: str
    name: str
    category: str
    price: float
    warranty_months: int

    model_config = ConfigDict(from_attributes=True)
