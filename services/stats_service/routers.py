from typing import Optional, Union
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from database import get_db
from patterns import (
    StatsServiceFacade,
    JsonReportFormatter,
    CsvReportFormatter,
)
from schemas import (
    StatsRequestsOut,
    StatsEmployeesOut,
    StatsProductsOut,
)

stats_router = APIRouter(prefix="/api/v1/stats", tags=["Statistics"])


def create_csv_response(csv_text: str, filename: str) -> Response:
    """Формирует HTTP-ответ со скачиваемым CSV-файлом в кодировке UTF-8 с BOM (для корректного открытия в Excel / Р-7 Офис)"""
    utf8_bom = "\ufeff" + csv_text
    return Response(
        content=utf8_bom.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@stats_router.get("/requests", summary="Статистика по сервисным заявкам за период")
def get_requests_stats(
    from_date: Optional[str] = Query(None, alias="from", description="Начальная дата периода (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, alias="to", description="Конечная дата периода (YYYY-MM-DD)"),
    format: str = Query("json", description="Формат ответа: json или csv"),
    db: Session = Depends(get_db),
):
    """
    Отчёт о заявках за выбранный период:
    - Общее количество и распределение по статусам
    - Средняя длительность обслуживания
    - Экспорт в CSV по форме Таблицы 3 Проектного решения (ПР)
    """
    facade = StatsServiceFacade(db)
    data = facade.calculate_requests_stats(from_date=from_date, to_date=to_date)

    if format.lower() == "csv":
        csv_content = CsvReportFormatter().format_requests(data)
        return create_csv_response(csv_content, "stats_requests.csv")

    return JsonReportFormatter().format_requests(data)


@stats_router.get("/employees", summary="Показатели работы сотрудников сервиса")
def get_employees_stats(
    from_date: Optional[str] = Query(None, alias="from", description="Начальная дата периода (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, alias="to", description="Конечная дата периода (YYYY-MM-DD)"),
    format: str = Query("json", description="Формат ответа: json или csv"),
    db: Session = Depends(get_db),
):
    """
    Отчёт о работе сотрудников сервиса:
    - Количество обработанных и активных заявок
    - Среднее время обработки по каждому сотруднику (в днях и часах)
    - Экспорт в CSV по форме Таблицы 4 Проектного решения (ПР)
    """
    facade = StatsServiceFacade(db)
    data = facade.calculate_employees_stats(from_date=from_date, to_date=to_date)

    if format.lower() == "csv":
        csv_content = CsvReportFormatter().format_employees(data)
        return create_csv_response(csv_content, "stats_employees.csv")

    return JsonReportFormatter().format_employees(data)


@stats_router.get("/products", summary="Рейтинг обращений по товарам")
def get_products_stats(
    from_date: Optional[str] = Query(None, alias="from", description="Начальная дата периода (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, alias="to", description="Конечная дата периода (YYYY-MM-DD)"),
    format: str = Query("json", description="Формат ответа: json или csv"),
    db: Session = Depends(get_db),
):
    """
    Отчёт об обращениях по товарам:
    - Рейтинг электротоваров по количеству гарантийных заявок (по убыванию)
    - Экспорт в CSV по форме Таблицы 5 Проектного решения (ПР)
    """
    facade = StatsServiceFacade(db)
    data = facade.calculate_products_stats(from_date=from_date, to_date=to_date)

    if format.lower() == "csv":
        csv_content = CsvReportFormatter().format_products(data)
        return create_csv_response(csv_content, "stats_products.csv")

    return JsonReportFormatter().format_products(data)
