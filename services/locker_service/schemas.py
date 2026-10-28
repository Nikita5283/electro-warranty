from pydantic import BaseModel, Field, ConfigDict


class CreateCellSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=20, description="Код ячейки постамата, например A-101")


class CellActionSchema(BaseModel):
    request_id: str = Field(..., min_length=1, max_length=8, description="ID заявки из request-service")


class CellOut(BaseModel):
    id: str
    code: str
    status: str
    request_id: str | None = None

    model_config = ConfigDict(from_attributes=True)
