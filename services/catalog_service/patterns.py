import os
import random
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models import ProductModel, PurchaseModel, AuditLogModel, utc_now, generate_short_id
from schemas import ProductCreateSchema, ProductUpdateSchema, PurchaseOut, InternalPurchaseOut, InternalProductOut

logger = logging.getLogger("catalog-service")


# Порождающий паттерн №1: Singleton (Одиночка)
# Гарантирует единственный экземпляр конфигурации микросервиса каталога в памяти
class CatalogConfigSingleton:
    _instance: Optional["CatalogConfigSingleton"] = None

    def __new__(cls) -> "CatalogConfigSingleton":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.seed_catalog = os.getenv("SEED_CATALOG", "true").lower() == "true"
            cls._instance.serial_prefix = os.getenv("SERIAL_PREFIX", "SN")
        return cls._instance


# Поведенческий паттерн №1: Strategy (Стратегия)
# Различные подходы к расчету даты окончания гарантии
class WarrantyCalculatorStrategy(ABC):
    @abstractmethod
    def calculate_warranty_end(self, start_date: datetime, months: int) -> datetime:
        pass


class StandardCalendarWarrantyCalculator(WarrantyCalculatorStrategy):
    """Стандартный календарный расчет: добавление месяцев к дате покупки"""
    def calculate_warranty_end(self, start_date: datetime, months: int) -> datetime:
        # Приближенно 30.5 дней на месяц с сохранением времени суток
        total_days = int(months * 30.4375)
        return start_date + timedelta(days=total_days)


# Порождающий паттерн №2: Factory Method / Generator (Фабрика серийных номеров)
class SerialNumberFactory:
    """Генерирует уникальный серийный номер для изделия по категории"""
    CATEGORY_PREFIXES = {
        "Смартфоны": "PHN",
        "Ноутбуки": "NBK",
        "Телевизоры": "TV",
        "Аудио": "AUD",
        "Бытовая техника": "APP",
    }

    @classmethod
    def generate(cls, category: str) -> str:
        prefix = cls.CATEGORY_PREFIXES.get(category, "DEV")
        random_code = random.randint(100000, 999999)
        checksum = random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ")
        return f"SN-{prefix}-{random_code}{checksum}"


# Поведенческий паттерн №2: Observer (Наблюдатель)
# Протоколирование действий пользователя в таблицу audit_log (раздел 9 ПР)
class AuditEvent:
    def __init__(self, entity: str, entity_id: str, action: str,
                 old_value: Optional[str] = None, new_value: Optional[str] = None,
                 changed_by: Optional[str] = None):
        self.entity = entity
        self.entity_id = entity_id
        self.action = action
        self.old_value = old_value
        self.new_value = new_value
        self.changed_by = changed_by


class CatalogAuditObserver:
    def __init__(self, db: Session):
        self.db = db

    def notify(self, event: AuditEvent) -> None:
        log_entry = AuditLogModel(
            entity=event.entity,
            entity_id=event.entity_id,
            action=event.action,
            old_value=event.old_value,
            new_value=event.new_value,
            changed_by=event.changed_by,
            changed_at=utc_now(),
        )
        self.db.add(log_entry)
        logger.info(
            f"Аудит [{event.entity}]: id={event.entity_id}, действие={event.action}, "
            f"пользователь={event.changed_by or 'SYSTEM'}"
        )


# Структурный паттерн №1: Facade (Фасад)
# Единая точка доступа к операциям каталога товаров и покупок
class CatalogServiceFacade:
    def __init__(self, db: Session):
        self.db = db
        self.config = CatalogConfigSingleton()
        self.audit = CatalogAuditObserver(db)
        self.warranty_calculator = StandardCalendarWarrantyCalculator()

    # Товары каталога

    def list_products(self, category: Optional[str] = None, search: Optional[str] = None) -> List[ProductModel]:
        stmt = select(ProductModel).where(ProductModel.is_active == True)
        if category:
            stmt = stmt.where(ProductModel.category == category)
        if search:
            stmt = stmt.where(ProductModel.name.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(ProductModel.category, ProductModel.name)
        return list(self.db.scalars(stmt).all())

    def get_product(self, product_id: str) -> ProductModel:
        product = self.db.get(ProductModel, product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=404, detail=f"Товар с id '{product_id}' не найден")
        return product

    def create_product(self, payload: ProductCreateSchema, user_id: Optional[str] = None) -> ProductModel:
        product_id = payload.id.strip().upper() if payload.id else generate_short_id()
        if self.db.get(ProductModel, product_id):
            raise HTTPException(status_code=409, detail=f"Товар с id '{product_id}' уже существует")

        product = ProductModel(
            id=product_id,
            name=payload.name.strip(),
            category=payload.category.strip(),
            price=payload.price,
            warranty_months=payload.warranty_months,
            is_active=True,
            created_at=utc_now(),
        )
        self.db.add(product)
        self.audit.notify(AuditEvent(
            entity="product",
            entity_id=product.id,
            action="CREATE",
            new_value=f"{product.name} ({product.category}, {product.price} руб., {product.warranty_months} мес.)",
            changed_by=user_id,
        ))
        self.db.commit()
        self.db.refresh(product)
        return product

    def update_product(self, product_id: str, payload: ProductUpdateSchema, user_id: Optional[str] = None) -> ProductModel:
        product = self.db.get(ProductModel, product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Товар с id '{product_id}' не найден")

        old_val = f"{product.name} ({product.price} руб., active={product.is_active})"
        if payload.name is not None:
            product.name = payload.name.strip()
        if payload.category is not None:
            product.category = payload.category.strip()
        if payload.price is not None:
            product.price = payload.price
        if payload.warranty_months is not None:
            product.warranty_months = payload.warranty_months
        if payload.is_active is not None:
            product.is_active = payload.is_active

        new_val = f"{product.name} ({product.price} руб., active={product.is_active})"
        self.audit.notify(AuditEvent(
            entity="product",
            entity_id=product.id,
            action="UPDATE",
            old_value=old_val,
            new_value=new_val,
            changed_by=user_id,
        ))
        self.db.commit()
        self.db.refresh(product)
        return product

    # Покупки клиентов

    def create_purchase(self, client_id: str, product_id: str, serial_number: Optional[str] = None) -> PurchaseModel:
        product = self.get_product(product_id)
        purchase_date = utc_now()
        warranty_until = self.warranty_calculator.calculate_warranty_end(purchase_date, product.warranty_months)

        sn = serial_number.strip().upper() if serial_number else SerialNumberFactory.generate(product.category)

        purchase = PurchaseModel(
            id=generate_short_id(),
            product_id=product.id,
            client_id=client_id,
            serial_number=sn,
            purchase_date=purchase_date,
            warranty_until=warranty_until,
        )
        self.db.add(purchase)
        self.audit.notify(AuditEvent(
            entity="purchase",
            entity_id=purchase.id,
            action="BUY",
            new_value=f"Покупка товара {product.name} клиентом {client_id}, SN: {sn}",
            changed_by=client_id,
        ))
        self.db.commit()
        self.db.refresh(purchase)
        return purchase

    def list_client_purchases(self, client_id: str) -> List[PurchaseOut]:
        stmt = (
            select(PurchaseModel)
            .options(selectinload(PurchaseModel.product))
            .where(PurchaseModel.client_id == client_id)
            .order_by(PurchaseModel.purchase_date.desc())
        )
        purchases = self.db.scalars(stmt).all()
        now = utc_now()

        result = []
        for p in purchases:
            # Сравниваем даты для определения валидности гарантии
            is_valid = p.warranty_until >= now
            result.append(PurchaseOut(
                id=p.id,
                product_id=p.product_id,
                client_id=p.client_id,
                serial_number=p.serial_number,
                purchase_date=p.purchase_date,
                warranty_until=p.warranty_until,
                is_warranty_valid=is_valid,
                product_name=p.product.name if p.product else None,
                product_category=p.product.category if p.product else None,
            ))
        return result

    def get_purchase(self, purchase_id: str) -> PurchaseOut:
        stmt = (
            select(PurchaseModel)
            .options(selectinload(PurchaseModel.product))
            .where(PurchaseModel.id == purchase_id)
        )
        purchase = self.db.scalar(stmt)
        if not purchase:
            raise HTTPException(status_code=404, detail=f"Покупка с id '{purchase_id}' не найдена")

        now = utc_now()
        return PurchaseOut(
            id=purchase.id,
            product_id=purchase.product_id,
            client_id=purchase.client_id,
            serial_number=purchase.serial_number,
            purchase_date=purchase.purchase_date,
            warranty_until=purchase.warranty_until,
            is_warranty_valid=purchase.warranty_until >= now,
            product_name=purchase.product.name if purchase.product else None,
            product_category=purchase.product.category if purchase.product else None,
        )

    # Межсервисные интерфейсы (/internal)

    def get_internal_purchase(self, purchase_id: str) -> InternalPurchaseOut:
        stmt = (
            select(PurchaseModel)
            .options(selectinload(PurchaseModel.product))
            .where(PurchaseModel.id == purchase_id)
        )
        purchase = self.db.scalar(stmt)
        if not purchase:
            raise HTTPException(status_code=404, detail="Покупка не найдена")

        return InternalPurchaseOut(
            id=purchase.id,
            client_id=purchase.client_id,
            product_id=purchase.product_id,
            serial_number=purchase.serial_number,
            purchase_date=purchase.purchase_date,
            warranty_until=purchase.warranty_until,
            product_name=purchase.product.name if purchase.product else "Электротовар",
        )

    def get_internal_product(self, product_id: str) -> InternalProductOut:
        product = self.db.get(ProductModel, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Товар не найден")

        return InternalProductOut(
            id=product.id,
            name=product.name,
            category=product.category,
            price=product.price,
            warranty_months=product.warranty_months,
        )

    # Сидирование начальных данных

    def seed_default_catalog(self) -> None:
        """Заполняет справочник электротоваров и покупки при первом запуске"""
        if not self.config.seed_catalog:
            return

        existing_count = len(self.db.scalars(select(ProductModel)).all())
        if existing_count > 0:
            return

        logger.info("Инициализация начального каталога электротоваров...")

        default_products = [
            ProductModel(
                id="PROD0001",
                name="Смартфон Galaxy S24 Ultra",
                category="Смартфоны",
                price=89990.0,
                warranty_months=24,
                is_active=True,
                created_at=utc_now(),
            ),
            ProductModel(
                id="PROD0002",
                name="Ноутбук ThinkPad X1 Carbon Gen 11",
                category="Ноутбуки",
                price=149990.0,
                warranty_months=36,
                is_active=True,
                created_at=utc_now(),
            ),
            ProductModel(
                id="PROD0003",
                name="Телевизор OLED Smart TV 55",
                category="Телевизоры",
                price=119990.0,
                warranty_months=24,
                is_active=True,
                created_at=utc_now(),
            ),
            ProductModel(
                id="PROD0004",
                name="Беспроводные наушники WH-1000XM5",
                category="Аудио",
                price=34990.0,
                warranty_months=12,
                is_active=True,
                created_at=utc_now(),
            ),
            ProductModel(
                id="PROD0005",
                name="Робот-пылесос RoboVac X8 Pro",
                category="Бытовая техника",
                price=42990.0,
                warranty_months=12,
                is_active=True,
                created_at=utc_now(),
            ),
            ProductModel(
                id="PROD0006",
                name="Кофемашина Barista Touch",
                category="Бытовая техника",
                price=67990.0,
                warranty_months=24,
                is_active=True,
                created_at=utc_now(),
            ),
        ]
        self.db.add_all(default_products)
        self.db.commit()

        # Создаем тестовые покупки для пользователя USER0001 (Иван)
        now = utc_now()
        default_purchases = [
            # 1. Покупка с действующей гарантией
            PurchaseModel(
                id="PUR00001",
                product_id="PROD0001",
                client_id="USER0001",
                serial_number="SN-PHN-882194A",
                purchase_date=now - timedelta(days=60),
                warranty_until=now + timedelta(days=670),
            ),
            # 2. Покупка с действующей гарантией
            PurchaseModel(
                id="PUR00002",
                product_id="PROD0002",
                client_id="USER0001",
                serial_number="SN-NBK-441209B",
                purchase_date=now - timedelta(days=30),
                warranty_until=now + timedelta(days=1060),
            ),
            # 3. Покупка с ИСТЕКШЕЙ гарантией (для проверки валидации отказа)
            PurchaseModel(
                id="EXPIRED1",
                product_id="PROD0004",
                client_id="USER0001",
                serial_number="SN-AUD-119283X",
                purchase_date=now - timedelta(days=800),
                warranty_until=now - timedelta(days=435),
            ),
        ]
        self.db.add_all(default_purchases)
        self.db.commit()

        logger.info(f"Каталог инициализирован: {len(default_products)} товаров, {len(default_purchases)} покупок.")
