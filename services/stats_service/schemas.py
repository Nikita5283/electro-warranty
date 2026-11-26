from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict


class RequestStatItem(BaseModel):
    id: str
    created_at: datetime
    closed_at: Optional[datetime] = None
    status: str
    product_id: Optional[str] = None
    product_name: str
    employee_id: Optional[str] = None
    employee_name: str
    duration_hours: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class StatsRequestsOut(BaseModel):
    """Сводная статистика по сервисным заявкам за период"""
    total_requests: int
    by_status: Dict[str, int]
    avg_duration_days: float
    avg_duration_hours: float
    requests: List[RequestStatItem]


class EmployeeStatItem(BaseModel):
    employee_id: str
    full_name: str
    completed_count: int
    in_progress_count: int
    avg_time_days: float
    avg_time_hours: float

    model_config = ConfigDict(from_attributes=True)


class StatsEmployeesOut(BaseModel):
    """Показатели эффективности работы сотрудников сервиса"""
    total_employees: int
    employees: List[EmployeeStatItem]


class ProductStatItem(BaseModel):
    product_id: str
    name: str
    category: str
    requests_count: int

    model_config = ConfigDict(from_attributes=True)


class StatsProductsOut(BaseModel):
    """Рейтинг электротоваров по количеству гарантийных обращений (по убыванию)"""
    total_claims: int
    products: List[ProductStatItem]
