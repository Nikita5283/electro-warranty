from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class RegisterSchema(BaseModel):
    email: str = Field(..., max_length=100, description="E-mail пользователя")
    password: str = Field(..., min_length=4, max_length=100, description="Пароль пользователя")
    full_name: str = Field(..., min_length=2, max_length=100, description="ФИО пользователя")
    phone: str = Field(..., min_length=5, max_length=20, description="Номер телефона")
    role: Optional[str] = Field("CLIENT", description="Роль пользователя (CLIENT, EMPLOYEE, MANAGER, ADMIN)")


class LoginSchema(BaseModel):
    email: str = Field(..., description="E-mail пользователя")
    password: str = Field(..., description="Пароль пользователя")


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class VerifyTokenSchema(BaseModel):
    token: str = Field(..., description="JWT-токен для проверки")


class VerifyTokenOut(BaseModel):
    user_id: str
    role: str
    email: Optional[str] = None
    full_name: Optional[str] = None


class InternalUserOut(BaseModel):
    id: str
    full_name: str
    role: str
    email: str
    phone: str

    model_config = ConfigDict(from_attributes=True)
