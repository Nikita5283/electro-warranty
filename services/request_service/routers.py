from typing import Optional, List

from fastapi import APIRouter, Depends, Header, Query, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    CreateRequestSchema,
    AssignRequestSchema,
    ChangeStatusSchema,
    ServiceRequestOut,
)
from patterns import RequestServiceFacade, STATE_MAP

router = APIRouter(prefix="/api/v1/requests", tags=["Requests"])


@router.get("/statuses", response_model=List[str])
def get_statuses():
    """Справочник статусов жизненного цикла заявки"""
    return list(STATE_MAP.keys())


@router.post("", response_model=ServiceRequestOut, status_code=201)
async def create_request(
    payload: CreateRequestSchema,
    x_user_id: str = Header(..., alias="X-User-Id", description="ID пользователя от API Gateway"),
    db: Session = Depends(get_db),
):
    """Создание гарантийной заявки клиентом (проверка гарантии в catalog-service)"""
    facade = RequestServiceFacade(db)
    return await facade.create_request(payload.purchase_id, payload.problem_description, x_user_id)


@router.get("", response_model=List[ServiceRequestOut])
def list_requests(
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    client_id: Optional[str] = Query(None, description="Фильтр по ID клиента"),
    db: Session = Depends(get_db),
):
    """Список заявок (очередь заявок для сотрудника сервиса или 'Мои заявки' для клиента)"""
    facade = RequestServiceFacade(db)
    return facade.list_requests(status, client_id)


@router.get("/{request_id}", response_model=ServiceRequestOut)
def get_request(request_id: str, db: Session = Depends(get_db)):
    """Получение карточки заявки вместе с историей статусов StatusHistory"""
    facade = RequestServiceFacade(db)
    return facade.get_request(request_id)


@router.post("/{request_id}/assign", response_model=ServiceRequestOut)
async def assign_request(
    request_id: str,
    payload: Optional[AssignRequestSchema] = None,
    x_user_id: str = Header(..., alias="X-User-Id", description="ID сотрудника сервиса от API Gateway"),
    db: Session = Depends(get_db),
):
    """Взятие заявки из очереди в работу сотрудником сервиса"""
    emp_id = (payload.employee_id if payload and payload.employee_id else None) or x_user_id
    if not emp_id:
        raise HTTPException(status_code=400, detail="Не указан ID сотрудника")
    facade = RequestServiceFacade(db)
    return await facade.assign_employee(request_id, emp_id)


@router.post("/{request_id}/status", response_model=ServiceRequestOut)
async def update_request_status(
    request_id: str,
    payload: ChangeStatusSchema,
    x_user_id: str = Header(..., alias="X-User-Id", description="ID сотрудника сервиса от API Gateway"),
    db: Session = Depends(get_db),
):
    """Последовательный перевод заявки по статусам (с занятием и освобождением ячейки постамата)"""
    facade = RequestServiceFacade(db)
    return await facade.change_status(
        request_id=request_id,
        new_status=payload.status,
        employee_id=x_user_id,
        cell_code=payload.cell_code,
        comment=payload.comment,
    )
