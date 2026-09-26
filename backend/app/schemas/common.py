from pydantic import BaseModel


class ApiError(BaseModel):
    error_code: str
    message: str
    correlation_id: str
    details: dict[str, str | int | float | bool | None] | None = None
