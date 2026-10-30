import os
import json
import base64
import hmac
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import UserModel, CLIENT, EMPLOYEE, MANAGER, ADMIN, VALID_ROLES

logger = logging.getLogger("users-service")


# Порождающий паттерн №1 singleton
# Гарантирует единственный экземпляр конфигурации сервиса пользователей в памяти
class UsersConfigSingleton:
    _instance: Optional["UsersConfigSingleton"] = None

    def __new__(cls) -> "UsersConfigSingleton":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.jwt_secret = os.getenv("JWT_SECRET", "electro-warranty-jwt-super-secret-key-2025")
            cls._instance.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
            cls._instance.token_expire_hours = int(os.getenv("TOKEN_EXPIRE_HOURS", "24"))
            cls._instance.seed_users = os.getenv("SEED_USERS", "true").lower() == "true"
        return cls._instance


# Паттерн Стратегия для безопасности: Безопасное хеширование паролей через PBKDF2-HMAC-SHA256
class PasswordHasher:
    ITERATIONS = 100_000

    @classmethod
    def hash_password(cls, password: str) -> str:
        salt = os.urandom(16).hex()
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            cls.ITERATIONS,
        )
        return f"pbkdf2_sha256${cls.ITERATIONS}${salt}${dk.hex()}"

    @classmethod
    def verify_password(cls, password: str, hashed: str) -> bool:
        try:
            parts = hashed.split("$")
            if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
                return False
            iterations = int(parts[1])
            salt = parts[2]
            expected_hex = parts[3]
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations,
            )
            return hmac.compare_digest(dk.hex(), expected_hex)
        except Exception as exc:
            logger.error(f"Ошибка проверки пароля: {exc}")
            return False


# Паттерн Провайдер / Фабрика токенов: Генерация и проверка JWT (RFC 7519, HS256)
class JwtTokenProvider:
    MOCK_USERS = {
        "client": {"user_id": "USER0001", "role": "CLIENT", "email": "client@example.com", "full_name": "Иванов Иван Иванович"},
        "employee": {"user_id": "EMP00001", "role": "EMPLOYEE", "email": "employee@example.com", "full_name": "Петров Пётр Сергеевич"},
        "manager": {"user_id": "MGR00001", "role": "MANAGER", "email": "manager@example.com", "full_name": "Сидоров Алексей Михайлович"},
        "admin": {"user_id": "ADM00001", "role": "ADMIN", "email": "admin@example.com", "full_name": "Администратор Системы"},
    }

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64url_decode(s: str) -> bytes:
        rem = len(s) % 4
        if rem > 0:
            s += "=" * (4 - rem)
        return base64.urlsafe_b64decode(s.encode("ascii"))

    @classmethod
    def create_token(cls, user_id: str, role: str, email: str) -> str:
        config = UsersConfigSingleton()
        now = datetime.now(timezone.utc)
        exp = now + timedelta(hours=config.token_expire_hours)

        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": user_id,
            "role": role,
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }

        h_b64 = cls._b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        p_b64 = cls._b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        sig = hmac.new(config.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        sig_b64 = cls._b64url_encode(sig)

        return f"{h_b64}.{p_b64}.{sig_b64}"

    @classmethod
    def verify_token(cls, token: str) -> Dict[str, Any]:
        # Поддержка mock-токенов для совместимости с окружением разработки и панелью
        token_lower = token.strip().lower()
        if token_lower in cls.MOCK_USERS:
            mock_data = cls.MOCK_USERS[token_lower]
            return {
                "sub": mock_data["user_id"],
                "role": mock_data["role"],
                "email": mock_data["email"],
                "full_name": mock_data["full_name"],
            }

        config = UsersConfigSingleton()
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Недействительный формат токена")

        h_b64, p_b64, sig_b64 = parts
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        expected_sig = cls._b64url_encode(
            hmac.new(config.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        )

        if not hmac.compare_digest(sig_b64, expected_sig):
            logger.warning("Отказ валидации токена: неверная цифровая подпись")
            raise HTTPException(status_code=401, detail="Недействительная подпись токена")

        try:
            payload = json.loads(cls._b64url_decode(p_b64).decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=401, detail="Некорректная полезная нагрузка токена")

        exp = payload.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            logger.warning(f"Отказ валидации токена: срок действия истёк ({exp})")
            raise HTTPException(status_code=401, detail="Срок действия токена истёк")

        return payload


# Поведенческий паттерн №1 chain of responsibility
# Последовательная валидация данных пользователя при регистрации
class UserValidationHandler(ABC):
    def __init__(self, next_handler: Optional["UserValidationHandler"] = None):
        self._next = next_handler

    def handle(self, db: Session, data: Dict[str, Any]) -> None:
        self._check(db, data)
        if self._next:
            self._next.handle(db, data)

    @abstractmethod
    def _check(self, db: Session, data: Dict[str, Any]) -> None:
        pass


class EmailUniquenessHandler(UserValidationHandler):
    """Звено 1: Проверка уникальности email адреса"""
    def _check(self, db: Session, data: Dict[str, Any]) -> None:
        email = data.get("email", "").strip().lower()
        if not email:
            raise HTTPException(status_code=422, detail="E-mail не может быть пустым")

        existing = db.scalar(select(UserModel).where(UserModel.email == email))
        if existing:
            logger.warning(f"Отказ в регистрации: email {email} уже используется")
            raise HTTPException(
                status_code=409,
                detail=f"Пользователь с адресом {email} уже зарегистрирован",
            )


class PasswordComplexityHandler(UserValidationHandler):
    """Звено 2: Проверка требований к сложности пароля"""
    def _check(self, db: Session, data: Dict[str, Any]) -> None:
        password = data.get("password", "")
        if len(password) < 4:
            raise HTTPException(
                status_code=422,
                detail="Пароль должен содержать не менее 4 символов",
            )


class RoleValidationHandler(UserValidationHandler):
    """Звено 3: Проверка допустимости роли пользователя"""
    def _check(self, db: Session, data: Dict[str, Any]) -> None:
        role = (data.get("role") or CLIENT).upper()
        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=422,
                detail=f"Недопустимая роль '{role}'. Допустимые роли: {', '.join(sorted(VALID_ROLES))}",
            )


# Поведенческий паттерн №2 observer
# Протоколирование событий безопасности и аудита пользователей
class UserObserver(ABC):
    @abstractmethod
    def on_event(self, event_type: str, user: UserModel, details: str) -> None:
        pass


class AuditLogObserver(UserObserver):
    """Подписчик: Протоколирует события авторизации и регистрации в системный лог"""
    def on_event(self, event_type: str, user: UserModel, details: str) -> None:
        logger.info(f"Событие безопасности [{event_type}]: Пользователь {user.id} ({user.email}, роль={user.role}) - {details}")


# Структурный паттерн №1 facade
# Единая точка входа в бизнес-логику управления пользователями и аутентификацией
class UsersServiceFacade:
    def __init__(self, db: Session):
        self.db = db
        self.config = UsersConfigSingleton()
        self.observers: List[UserObserver] = [AuditLogObserver()]

    def _notify(self, event_type: str, user: UserModel, details: str) -> None:
        for observer in self.observers:
            try:
                observer.on_event(event_type, user, details)
            except Exception as exc:
                logger.error(f"Ошибка в наблюдателе аудита: {exc}")

    def register(self, email: str, password: str, full_name: str, phone: str, role: Optional[str] = None) -> tuple[UserModel, str]:
        role = (role or CLIENT).upper()
        registration_data = {
            "email": email.strip().lower(),
            "password": password,
            "full_name": full_name.strip(),
            "phone": phone.strip(),
            "role": role,
        }

        # 1. Валидация через Chain of Responsibility
        chain = EmailUniquenessHandler(
            next_handler=PasswordComplexityHandler(
                next_handler=RoleValidationHandler()
            )
        )
        chain.handle(self.db, registration_data)

        # 2. Хеширование пароля
        password_hash = PasswordHasher.hash_password(password)

        # 3. Сохранение в БД
        new_user = UserModel(
            email=registration_data["email"],
            password_hash=password_hash,
            full_name=registration_data["full_name"],
            phone=registration_data["phone"],
            role=role,
        )
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)

        # 4. Уведомление наблюдателей
        self._notify("REGISTER", new_user, "Успешная регистрация нового аккаунта")

        # 5. Генерация JWT-токена
        token = JwtTokenProvider.create_token(new_user.id, new_user.role, new_user.email)
        return new_user, token

    def login(self, email: str, password: str) -> tuple[UserModel, str]:
        clean_email = email.strip().lower()
        user = self.db.scalar(select(UserModel).where(UserModel.email == clean_email))
        if not user or not PasswordHasher.verify_password(password, user.password_hash):
            logger.warning(f"Отказ в аутентификации: неверные учетные данные для email {clean_email}")
            raise HTTPException(status_code=401, detail="Неверный email или пароль")

        self._notify("LOGIN", user, "Успешный вход в систему")
        token = JwtTokenProvider.create_token(user.id, user.role, user.email)
        return user, token

    def verify_token(self, token: str) -> Dict[str, Any]:
        payload = JwtTokenProvider.verify_token(token)
        user_id = payload.get("sub")
        role = payload.get("role")

        # Если токен валиден, пытаемся обогатить данными пользователя из БД при наличии
        user = self.db.get(UserModel, user_id)
        if user:
            return {
                "user_id": user.id,
                "role": user.role,
                "email": user.email,
                "full_name": user.full_name,
            }

        return {
            "user_id": str(user_id),
            "role": str(role).upper() if role else CLIENT,
            "email": payload.get("email"),
            "full_name": payload.get("full_name"),
        }

    def get_user_by_id(self, user_id: str) -> UserModel:
        user = self.db.get(UserModel, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return user

    def list_users(self, role: Optional[str] = None) -> List[UserModel]:
        stmt = select(UserModel).order_by(UserModel.created_at.desc())
        if role:
            stmt = stmt.where(UserModel.role == role.upper())
        return list(self.db.scalars(stmt).all())

    def seed_default_users(self) -> None:
        """Инициализация тестовых пользователей системы при первом запуске"""
        default_users = [
            ("USER0001", "client@example.com", "client123", "Иванов Иван Иванович", "+79001112233", CLIENT),
            ("EMP00001", "employee@example.com", "employee123", "Петров Пётр Сергеевич", "+79002223344", EMPLOYEE),
            ("MGR00001", "manager@example.com", "manager123", "Сидоров Алексей Михайлович", "+79003334455", MANAGER),
            ("ADM00001", "admin@example.com", "admin123", "Администратор Системы", "+79004445566", ADMIN),
        ]

        created_count = 0
        for uid, email, pwd, name, phone, role in default_users:
            existing = self.db.scalar(select(UserModel).where((UserModel.id == uid) | (UserModel.email == email)))
            if not existing:
                pwd_hash = PasswordHasher.hash_password(pwd)
                user = UserModel(
                    id=uid,
                    email=email,
                    password_hash=pwd_hash,
                    full_name=name,
                    phone=phone,
                    role=role,
                )
                self.db.add(user)
                created_count += 1

        if created_count > 0:
            self.db.commit()
            logger.info(f"Инициализировано тестовых пользователей: {created_count}")
