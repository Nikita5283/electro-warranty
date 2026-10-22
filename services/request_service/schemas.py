from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, ConfigDict


class CreateRequestSchema(BaseModel):
    purchase_id: str = Field(..., max_length=8, description="ID покупки из catalog-service")
    problem_description: str = Field(..., max_length=500, description="Описание проблемы со слов клиента")


class AssignRequestSchema(BaseModel):
    employee_id: str | None = Field(None, max_length=8, description="ID сотрудника сервиса")


class ChangeStatusSchema(BaseModel):
    status: str = Field(..., max_length=50, description="Новый статус заявки")
    cell_code: str | None = Field(
        None, max_length=20, description="Код ячейки постамата (обязателен для статуса 'товар обслужен')"
    )
    comment: str | None = Field(None, max_length=500, description="Комментарий к смене статуса")


class StatusHistoryOut(BaseModel):
    id: str
    status: str
    employee_id: str | None
    changed_at: datetime
    comment: str | None

    model_config = ConfigDict(from_attributes=True)


class ServiceRequestOut(BaseModel):
    id: str
    purchase_id: str
    client_id: str
    product_id: str | None
    employee_id: str | None
    problem_description: str
    status: str
    cell_code: str | None
    created_at: datetime
    closed_at: datetime | None
    history: List[StatusHistoryOut] = []

    model_config = ConfigDict(from_attributes=True)
