from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    """Vista publica del usuario. NUNCA incluye password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    workspace_id: int
    workspace_name: str


class LoginResponse(BaseModel):
    user: UserOut
