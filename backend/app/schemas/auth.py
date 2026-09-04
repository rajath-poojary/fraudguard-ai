from pydantic import BaseModel, Field, field_validator


class AuthCredentials(BaseModel):
    email: str = Field(min_length=4, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("email must be valid")
        return value


class RegisterRequest(AuthCredentials):
    display_name: str | None = Field(default=None, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    role: str
