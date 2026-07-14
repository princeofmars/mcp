from __future__ import annotations

import re

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import Agent, Tenant
from app.security import hash_key
from app.tool_registry import DEFAULT_AGENT_TOOLS, DEFAULT_PURPOSES


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:90] or "tenant"


def seed_demo() -> None:
    settings = get_settings()
    if not settings.seed_demo:
        return
    with SessionLocal() as db:
        existing = db.scalar(select(Tenant).where(Tenant.slug == "demo-insurer"))
        if existing:
            return
        tenant = Tenant(
            name="Demo Insurer",
            slug="demo-insurer",
            admin_key_hash=hash_key(settings.demo_admin_key),
        )
        db.add(tenant)
        db.flush()
        db.add(
            Agent(
                tenant_id=tenant.id,
                name="Demo Prevention Agent",
                environment="development",
                token_hash=hash_key(settings.demo_agent_key),
                allowed_tools=DEFAULT_AGENT_TOOLS.copy(),
                allowed_purposes=DEFAULT_PURPOSES.copy(),
            )
        )
        db.commit()


def initialize() -> None:
    init_db()
    seed_demo()
