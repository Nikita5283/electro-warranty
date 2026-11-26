import io
import csv
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models import ServiceRequestModel, StatusHistoryModel
from clients import ExternalServiceAdapter
from schemas import (
    RequestStatItem,
    StatsRequestsOut,
    EmployeeStatItem,
    StatsEmployeesOut,
    ProductStatItem,
    StatsProductsOut,
)

logger = logging.getLogger("stats-service")


def parse_date(date_str: Optional[str], default: Optional[datetime] = None) -> Optional[datetime]:
    if not date_str:
        return default
    try:
        # Поддерживаем YYYY-MM-DD и ISO 8601
        dt = datetime.fromisoformat(date_str.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return default


# Поведенческий паттерн №1: Strategy
# Различные стратегии экспорта и форматирования аналитической отчётности
class ReportFormatterStrategy(ABC):
    @abstractmethod
    def format_requests(self, data: StatsRequestsOut) -> Any:
        pass

    @abstractmethod
    def format_employees(self, data: StatsEmployeesOut) -> Any:
        pass

    @abstractmethod
    def format_products(self, data: StatsProductsOut) -> Any:
        pass


class JsonReportFormatter(ReportFormatterStrategy):
    """Стратегия форматирования отчетов в структурированный JSON"""
    def format_requests(self, data: StatsRequestsOut) -> StatsRequestsOut:
        return data

    def format_employees(self, data: StatsEmployeesOut) -> StatsEmployeesOut:
        return data

    def format_products(self, data: StatsProductsOut) -> StatsProductsOut:
        return data


class CsvReportFormatter(ReportFormatterStrategy):
    """Стратегия экспорта в CSV-файлы строго по шаблонам Таблиц 3, 4, 5 Проектного решения (ПР)"""
    def format_requests(self, data: StatsRequestsOut) -> str:
        # Табл. 3: № заявки;Дата создания;Товар;Сотрудник;Статус;Дата закрытия
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["№ заявки", "Дата создания", "Товар", "Сотрудник", "Статус", "Дата закрытия"])
        for r in data.requests:
            created = r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
            closed = r.closed_at.strftime("%Y-%m-%d %H:%M:%S") if r.closed_at else "В работе"
            writer.writerow([r.id, created, r.product_name, r.employee_name, r.status, closed])
        return output.getvalue()

    def format_employees(self, data: StatsEmployeesOut) -> str:
        # Табл. 4: ФИО сотрудника;Обработано заявок;Среднее время обработки, дн.
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["ФИО сотрудника", "Обработано заявок", "Среднее время обработки, дн."])
        for emp in data.employees:
            writer.writerow([emp.full_name, emp.completed_count, f"{emp.avg_time_days:.2f}"])
        return output.getvalue()

    def format_products(self, data: StatsProductsOut) -> str:
        # Табл. 5: Товар;Категория;Количество заявок
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["Товар", "Категория", "Количество заявок"])
        for prod in data.products:
            writer.writerow([prod.name, prod.category, prod.requests_count])
        return output.getvalue()


# Структурный паттерн №2: Facade
# Единая точка доступа к расчету аналитических показателей и отчетов
class StatsServiceFacade:
    def __init__(self, db: Session, adapter: Optional[ExternalServiceAdapter] = None):
        self.db = db
        self.adapter = adapter or ExternalServiceAdapter()

    def _get_filtered_requests(self, from_date: Optional[str], to_date: Optional[str]) -> List[ServiceRequestModel]:
        stmt = select(ServiceRequestModel).options(selectinload(ServiceRequestModel.history))
        dt_from = parse_date(from_date)
        dt_to = parse_date(to_date)

        if dt_from:
            stmt = stmt.where(ServiceRequestModel.created_at >= dt_from)
        if dt_to:
            # Учитываем весь день до 23:59:59
            if len(to_date.strip()) <= 10:
                dt_to = dt_to + timedelta(hours=23, minutes=59, seconds=59)
            stmt = stmt.where(ServiceRequestModel.created_at <= dt_to)

        stmt = stmt.order_by(ServiceRequestModel.created_at.desc())
        return list(self.db.scalars(stmt).all())

    # Отчёт 1: Статистика по заявкам

    def calculate_requests_stats(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> StatsRequestsOut:
        requests = self._get_filtered_requests(from_date, to_date)
        by_status: Dict[str, int] = {}
        durations_hours: List[float] = []

        items: List[RequestStatItem] = []
        for req in requests:
            by_status[req.status] = by_status.get(req.status, 0) + 1

            dur_hours = None
            if req.closed_at and req.created_at:
                delta = req.closed_at - req.created_at
                dur_hours = max(0.0, delta.total_seconds() / 3600.0)
                durations_hours.append(dur_hours)

            prod_info = self.adapter.get_product_info(req.product_id)
            emp_name = self.adapter.get_employee_name(req.employee_id)

            items.append(RequestStatItem(
                id=req.id,
                created_at=req.created_at,
                closed_at=req.closed_at,
                status=req.status,
                product_id=req.product_id,
                product_name=prod_info["name"],
                employee_id=req.employee_id,
                employee_name=emp_name,
                duration_hours=round(dur_hours, 2) if dur_hours is not None else None,
            ))

        avg_hours = sum(durations_hours) / len(durations_hours) if durations_hours else 0.0
        avg_days = avg_hours / 24.0

        return StatsRequestsOut(
            total_requests=len(requests),
            by_status=by_status,
            avg_duration_days=round(avg_days, 2),
            avg_duration_hours=round(avg_hours, 2),
            requests=items,
        )

    # Отчёт 2: Статистика по сотрудникам

    def calculate_employees_stats(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> StatsEmployeesOut:
        requests = self._get_filtered_requests(from_date, to_date)
        emp_completed: Dict[str, List[float]] = {}
        emp_in_progress: Dict[str, int] = {}

        for req in requests:
            emp_id = req.employee_id or "UNASSIGNED"
            if req.status == "товар выдан покупателю" or req.closed_at is not None:
                if emp_id not in emp_completed:
                    emp_completed[emp_id] = []
                dur_hours = 0.0
                if req.closed_at and req.created_at:
                    delta = req.closed_at - req.created_at
                    dur_hours = max(0.0, delta.total_seconds() / 3600.0)
                emp_completed[emp_id].append(dur_hours)
            else:
                emp_in_progress[emp_id] = emp_in_progress.get(emp_id, 0) + 1

        all_employees = set(emp_completed.keys()) | set(emp_in_progress.keys())
        employees_list: List[EmployeeStatItem] = []

        for emp_id in sorted(all_employees):
            if emp_id == "UNASSIGNED":
                full_name = "Не назначен (в очереди)"
            else:
                full_name = self.adapter.get_employee_name(emp_id)

            completed_durations = emp_completed.get(emp_id, [])
            completed_count = len(completed_durations)
            avg_hours = sum(completed_durations) / completed_count if completed_count > 0 else 0.0
            avg_days = avg_hours / 24.0

            employees_list.append(EmployeeStatItem(
                employee_id=emp_id,
                full_name=full_name,
                completed_count=completed_count,
                in_progress_count=emp_in_progress.get(emp_id, 0),
                avg_time_days=round(avg_days, 2),
                avg_time_hours=round(avg_hours, 2),
            ))

        return StatsEmployeesOut(
            total_employees=len(employees_list),
            employees=employees_list,
        )

    # Отчёт 3: Статистика по товарам

    def calculate_products_stats(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> StatsProductsOut:
        requests = self._get_filtered_requests(from_date, to_date)
        product_counts: Dict[str, int] = {}

        for req in requests:
            pid = req.product_id or "UNKNOWN"
            product_counts[pid] = product_counts.get(pid, 0) + 1

        # Сортировка по количеству обращений по убыванию (как требует ПР)
        sorted_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)
        items: List[ProductStatItem] = []

        for pid, count in sorted_products:
            prod_info = self.adapter.get_product_info(pid)
            items.append(ProductStatItem(
                product_id=pid,
                name=prod_info["name"],
                category=prod_info["category"],
                requests_count=count,
            ))

        return StatsProductsOut(
            total_claims=len(requests),
            products=items,
        )

    # Инициализация демо-заявок при пустой БД

    def seed_demo_requests_if_empty(self) -> None:
        """Если база заявок пустая, заполняет её репрезентативными данными для демонстрации отчётов"""
        count = len(self.db.scalars(select(ServiceRequestModel)).all())
        if count > 0:
            return

        logger.info("Инициализация демонстрационных заявок в requests_db...")
        now = datetime.now(timezone.utc)

        sample_requests = [
            # 1. Завершена
            ServiceRequestModel(
                id="REQ00001",
                purchase_id="PUR00001",
                client_id="USER0001",
                product_id="PROD0001",
                employee_id="EMP00001",
                problem_description="Перестал включаться экран после обновления",
                status="товар выдан покупателю",
                cell_code="A-101",
                created_at=now - timedelta(days=5, hours=4),
                closed_at=now - timedelta(days=2, hours=1),
            ),
            # 2. Завершена
            ServiceRequestModel(
                id="REQ00002",
                purchase_id="PUR00002",
                client_id="USER0001",
                product_id="PROD0002",
                employee_id="EMP00001",
                problem_description="Не работает клавиатура в верхнем ряду",
                status="товар выдан покупателю",
                cell_code="B-201",
                created_at=now - timedelta(days=8),
                closed_at=now - timedelta(days=4, hours=2),
            ),
            # 3. В ячейке постамата (обслужен)
            ServiceRequestModel(
                id="REQ00003",
                purchase_id="PUR00001",
                client_id="USER0001",
                product_id="PROD0001",
                employee_id="EMP00001",
                problem_description="Быстро разряжается аккумулятор",
                status="товар обслужен",
                cell_code="A-102",
                created_at=now - timedelta(days=2),
                closed_at=None,
            ),
            # 4. На обслуживании
            ServiceRequestModel(
                id="REQ00004",
                purchase_id="PUR00002",
                client_id="USER0001",
                product_id="PROD0003",
                employee_id="EMP00001",
                problem_description="Полосы на матрице телевизора",
                status="товар на обслуживании",
                cell_code=None,
                created_at=now - timedelta(days=1),
                closed_at=None,
            ),
            # 5. В очереди
            ServiceRequestModel(
                id="REQ00005",
                purchase_id="PUR00001",
                client_id="USER0001",
                product_id="PROD0005",
                employee_id=None,
                problem_description="Робот-пылесос не находит базу",
                status="принят",
                cell_code=None,
                created_at=now - timedelta(hours=3),
                closed_at=None,
            ),
        ]
        self.db.add_all(sample_requests)
        self.db.commit()

        # Добавляем историю статусов для завершенной заявки REQ00001
        history_items = [
            StatusHistoryModel(
                id="HST00001",
                request_id="REQ00001",
                status="принят",
                employee_id="EMP00001",
                changed_at=now - timedelta(days=5, hours=4),
                comment="Заявка принята в системе",
            ),
            StatusHistoryModel(
                id="HST00002",
                request_id="REQ00001",
                status="товар принят в сервис",
                employee_id="EMP00001",
                changed_at=now - timedelta(days=4, hours=6),
                comment="Товар доставлен в сервисный центр",
            ),
            StatusHistoryModel(
                id="HST00003",
                request_id="REQ00001",
                status="товар на обслуживании",
                employee_id="EMP00001",
                changed_at=now - timedelta(days=3, hours=8),
                comment="Диагностика и замена шлейфа дисплея",
            ),
            StatusHistoryModel(
                id="HST00004",
                request_id="REQ00001",
                status="товар обслужен",
                employee_id="EMP00001",
                changed_at=now - timedelta(days=2, hours=5),
                comment="Ремонт завершён, товар помещён в ячейку A-101",
            ),
            StatusHistoryModel(
                id="HST00005",
                request_id="REQ00001",
                status="товар выдан покупателю",
                employee_id="EMP00001",
                changed_at=now - timedelta(days=2, hours=1),
                comment="Покупатель забрал товар из ячейки",
            ),
        ]
        self.db.add_all(history_items)
        self.db.commit()
        logger.info("Демонстрационные заявки успешно созданы.")
