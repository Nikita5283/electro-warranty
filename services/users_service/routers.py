from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    RegisterSchema,
    LoginSchema,
    UserOut,
    AuthResponse,
    VerifyTokenSchema,
    VerifyTokenOut,
    InternalUserOut,
)
from patterns import UsersServiceFacade

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
users_router = APIRouter(prefix="/api/v1/users", tags=["Users"])
internal_router = APIRouter(prefix="/internal", tags=["Internal"])


@auth_router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterSchema, db: Session = Depends(get_db)):
    """Регистрация нового пользователя в системе"""
    facade = UsersServiceFacade(db)
    user, token = facade.register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
    )
    return AuthResponse(access_token=token, token_type="bearer", user=user)


@auth_router.post("/login", response_model=AuthResponse)
def login(payload: LoginSchema, db: Session = Depends(get_db)):
    """Вход пользователя в систему с выдачей JWT-токена"""
    facade = UsersServiceFacade(db)
    user, token = facade.login(email=payload.email, password=payload.password)
    return AuthResponse(access_token=token, token_type="bearer", user=user)


@users_router.get("", response_model=List[UserOut])
def list_users(
    role: Optional[str] = Query(None, description="Фильтр по роли пользователя (CLIENT, EMPLOYEE, MANAGER, ADMIN)"),
    db: Session = Depends(get_db),
):
    """Список пользователей системы"""
    facade = UsersServiceFacade(db)
    return facade.list_users(role=role)


@users_router.get("/{id}", response_model=UserOut)
def get_user(id: str, db: Session = Depends(get_db)):
    """Получение профиля пользователя по его ID"""
    facade = UsersServiceFacade(db)
    return facade.get_user_by_id(id)


@internal_router.post("/auth/verify", response_model=VerifyTokenOut)
def verify_token(payload: VerifyTokenSchema, db: Session = Depends(get_db)):
    """Внутренний эндпоинт проверки JWT-токена (вызывается API Gateway)"""
    facade = UsersServiceFacade(db)
    return facade.verify_token(payload.token)


@internal_router.get("/users/{id}", response_model=InternalUserOut)
def get_internal_user(id: str, db: Session = Depends(get_db)):
    """Внутренний эндпоинт получения данных пользователя (вызывается stats-service для отчётов)"""
    facade = UsersServiceFacade(db)
    return facade.get_user_by_id(id)
