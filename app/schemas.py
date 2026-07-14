from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.tool_registry import DEFAULT_AGENT_TOOLS, DEFAULT_PURPOSES


class OnboardRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=200)
    admin_email: EmailStr


class OnboardResponse(BaseModel):
    tenant_id: str
    tenant_slug: str
    admin_key: str
    message: str


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    environment: str = "production"
    allowed_tools: list[str] = Field(default_factory=lambda: DEFAULT_AGENT_TOOLS.copy())
    allowed_purposes: list[str] = Field(default_factory=lambda: DEFAULT_PURPOSES.copy())

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        if value not in {"development", "staging", "production"}:
            raise ValueError("environment must be development, staging or production")
        return value


class AgentCreated(BaseModel):
    id: str
    name: str
    token: str
    environment: str
    allowed_tools: list[str]
    allowed_purposes: list[str]


class AgentPublic(BaseModel):
    id: str
    name: str
    environment: str
    status: str
    allowed_tools: list[str]
    allowed_purposes: list[str]
    created_at: datetime
    last_seen_at: datetime | None


class PermissionUpdate(BaseModel):
    allowed_tools: list[str]
    allowed_purposes: list[str]


class CredentialCreate(BaseModel):
    provider: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=120)
    secret: str = Field(min_length=1, max_length=10000)


class CredentialPublic(BaseModel):
    id: str
    provider: str
    name: str
    created_at: datetime
    updated_at: datetime
