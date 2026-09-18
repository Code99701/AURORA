from pydantic import BaseModel
from app.schemas.user import UserRead

class LoginResponse(BaseModel):
    status: str = "success"
    user: UserRead

class LogoutResponse(BaseModel):
    status: str = "success"
    message: str = "Logged out successfully"


class AuthProviderState(BaseModel):
    enabled: bool


class AuthProvidersResponse(BaseModel):
    google: AuthProviderState
