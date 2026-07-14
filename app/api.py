from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import quantiles

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bootstrap import initialize, slugify
from app.db import get_db
from app.models import Agent, AuditEvent, Credential, Tenant
from app.schemas import (
    AgentCreate,
    AgentCreated,
    AgentPublic,
    CredentialCreate,
    CredentialPublic,
    OnboardRequest,
    OnboardResponse,
    PermissionUpdate,
)
from app.security import encrypt_secret, hash_key, issue_key
from app.tool_registry import DEFAULT_AGENT_TOOLS, TOOLS

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Enterprise MCP Gateway Admin", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def startup() -> None:
    initialize()


def admin_tenant(
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
    db: Session = Depends(get_db),
) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.admin_key_hash == hash_key(x_admin_key)))
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    return tenant


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "admin"}


@app.post("/api/v1/onboard", response_model=OnboardResponse, status_code=201)
def onboard(payload: OnboardRequest, db: Session = Depends(get_db)) -> OnboardResponse:
    base = slugify(payload.organization_name)
    slug = base
    suffix = 1
    while db.scalar(select(Tenant.id).where(Tenant.slug == slug)):
        suffix += 1
        slug = f"{base}-{suffix}"
    key = issue_key("adm")
    tenant = Tenant(name=payload.organization_name, slug=slug, admin_key_hash=key.digest)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return OnboardResponse(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        admin_key=key.plaintext,
        message="Store this admin key securely. It is shown only once.",
    )


@app.get("/api/v1/tenant")
def get_tenant(tenant: Tenant = Depends(admin_tenant)) -> dict:
    return {"id": tenant.id, "name": tenant.name, "slug": tenant.slug, "created_at": tenant.created_at}


@app.get("/api/v1/tools")
def list_tools(tenant: Tenant = Depends(admin_tenant)) -> list[dict]:
    del tenant
    return [tool.public_dict() for tool in TOOLS.values()]


@app.get("/api/v1/agents", response_model=list[AgentPublic])
def list_agents(tenant: Tenant = Depends(admin_tenant), db: Session = Depends(get_db)) -> list[Agent]:
    return list(db.scalars(select(Agent).where(Agent.tenant_id == tenant.id).order_by(Agent.created_at.desc())))


@app.post("/api/v1/agents", response_model=AgentCreated, status_code=201)
def create_agent(payload: AgentCreate, tenant: Tenant = Depends(admin_tenant), db: Session = Depends(get_db)) -> AgentCreated:
    unknown = sorted(set(payload.allowed_tools) - set(TOOLS))
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown tools: {', '.join(unknown)}")
    known_purposes = {purpose for tool in TOOLS.values() for purpose in tool.purposes}
    unknown_purposes = sorted(set(payload.allowed_purposes) - known_purposes)
    if unknown_purposes:
        raise HTTPException(status_code=400, detail=f"Unknown purposes: {', '.join(unknown_purposes)}")
    key = issue_key("mcp")
    agent = Agent(
        tenant_id=tenant.id,
        name=payload.name,
        environment=payload.environment,
        token_hash=key.digest,
        allowed_tools=payload.allowed_tools,
        allowed_purposes=payload.allowed_purposes,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return AgentCreated(
        id=agent.id,
        name=agent.name,
        token=key.plaintext,
        environment=agent.environment,
        allowed_tools=agent.allowed_tools,
        allowed_purposes=agent.allowed_purposes,
    )


@app.put("/api/v1/agents/{agent_id}/permissions", response_model=AgentPublic)
def update_permissions(
    agent_id: str,
    payload: PermissionUpdate,
    tenant: Tenant = Depends(admin_tenant),
    db: Session = Depends(get_db),
) -> Agent:
    agent = db.scalar(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant.id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    unknown = sorted(set(payload.allowed_tools) - set(TOOLS))
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown tools: {', '.join(unknown)}")
    agent.allowed_tools = payload.allowed_tools
    agent.allowed_purposes = payload.allowed_purposes
    db.commit()
    db.refresh(agent)
    return agent


@app.post("/api/v1/agents/{agent_id}/rotate-token")
def rotate_agent_token(agent_id: str, tenant: Tenant = Depends(admin_tenant), db: Session = Depends(get_db)) -> dict:
    agent = db.scalar(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant.id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    key = issue_key("mcp")
    agent.token_hash = key.digest
    db.commit()
    return {"agent_id": agent.id, "token": key.plaintext, "message": "Previous token was invalidated"}


@app.post("/api/v1/credentials", response_model=CredentialPublic, status_code=201)
def upsert_credential(
    payload: CredentialCreate,
    tenant: Tenant = Depends(admin_tenant),
    db: Session = Depends(get_db),
) -> Credential:
    provider = re.sub(r"[^a-zA-Z0-9_.-]", "", payload.provider)
    credential = db.scalar(
        select(Credential).where(
            Credential.tenant_id == tenant.id,
            Credential.provider == provider,
            Credential.name == payload.name,
        )
    )
    if credential:
        credential.encrypted_value = encrypt_secret(payload.secret)
        credential.updated_at = datetime.now(timezone.utc)
    else:
        credential = Credential(
            tenant_id=tenant.id,
            provider=provider,
            name=payload.name,
            encrypted_value=encrypt_secret(payload.secret),
        )
        db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential


@app.get("/api/v1/credentials", response_model=list[CredentialPublic])
def list_credentials(tenant: Tenant = Depends(admin_tenant), db: Session = Depends(get_db)) -> list[Credential]:
    return list(
        db.scalars(select(Credential).where(Credential.tenant_id == tenant.id).order_by(Credential.updated_at.desc()))
    )


@app.get("/api/v1/audit")
def audit_events(
    limit: int = Query(100, ge=1, le=500),
    tenant: Tenant = Depends(admin_tenant),
    db: Session = Depends(get_db),
) -> list[dict]:
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.tenant_id == tenant.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "trace_id": e.trace_id,
            "created_at": e.created_at,
            "agent_name": e.agent_name,
            "tool_name": e.tool_name,
            "purpose": e.purpose,
            "status": e.status,
            "policy_decision": e.policy_decision,
            "policy_reason": e.policy_reason,
            "latency_ms": round(e.latency_ms, 2),
            "error_type": e.error_type,
        }
        for e in events
    ]


@app.get("/api/v1/analytics/timeseries")
def analytics_timeseries(
    hours: int = Query(24, ge=1, le=24 * 30),
    tenant: Tenant = Depends(admin_tenant),
    db: Session = Depends(get_db),
) -> dict:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(hours=hours - 1)
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.tenant_id == tenant.id, AuditEvent.created_at >= start)
        )
    )
    buckets = {}
    for offset in range(hours):
        point = start + timedelta(hours=offset)
        buckets[point] = {"start": point.isoformat(), "calls": 0, "success": 0, "denied": 0, "error": 0}
    for event in events:
        created = event.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        key = created.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        if key in buckets:
            buckets[key]["calls"] += 1
            if event.status in {"success", "denied", "error"}:
                buckets[key][event.status] += 1
    return {"window_hours": hours, "buckets": list(buckets.values())}


@app.get("/api/v1/analytics/summary")
def analytics_summary(
    hours: int = Query(24, ge=1, le=24 * 90),
    tenant: Tenant = Depends(admin_tenant),
    db: Session = Depends(get_db),
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.tenant_id == tenant.id, AuditEvent.created_at >= since)
        )
    )
    total = len(events)
    success = sum(1 for e in events if e.status == "success")
    denied = sum(1 for e in events if e.status == "denied")
    errors = sum(1 for e in events if e.status == "error")
    latencies = sorted(e.latency_ms for e in events)
    p95 = 0.0
    if latencies:
        index = max(0, min(len(latencies) - 1, int(round(0.95 * (len(latencies) - 1)))))
        p95 = latencies[index]
    tool_counts = Counter(e.tool_name for e in events)
    status_counts = Counter(e.status for e in events)
    active_agents = db.scalar(
        select(func.count(Agent.id)).where(Agent.tenant_id == tenant.id, Agent.status == "active")
    ) or 0
    return {
        "window_hours": hours,
        "total_calls": total,
        "successful_calls": success,
        "denied_calls": denied,
        "error_calls": errors,
        "success_rate": round(success / total, 4) if total else 0,
        "p95_latency_ms": round(p95, 2),
        "active_agents": active_agents,
        "tool_usage": [{"tool": name, "count": count} for name, count in tool_counts.most_common()],
        "status_counts": dict(status_counts),
    }
