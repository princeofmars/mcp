from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.bootstrap import initialize
from app.config import get_settings
from app.db import SessionLocal
from app.models import Agent, AuditEvent
from app.policy import AgentPrincipal, PolicyDenied, authorize
from app.security import hash_key, member_hash
from app.services import (
    assess_data_quality as service_assess_data_quality,
    get_activity_summary as service_get_activity_summary,
    get_connection_status as service_get_connection_status,
    prepare_prevention_brief as service_prepare_prevention_brief,
    verify_reward_eligibility as service_verify_reward_eligibility,
)
from app.tool_registry import TOOLS

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("enterprise-mcp-gateway")

current_principal: ContextVar[AgentPrincipal | None] = ContextVar("current_principal", default=None)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in {"/health", "/.well-known/oauth-protected-resource"}:
            return await call_next(request)
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            return JSONResponse(
                {"error": "unauthorized", "message": "Bearer token required"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer scope="mcp:invoke"'},
            )
        token_hash = hash_key(header.split(" ", 1)[1].strip())
        with SessionLocal() as db:
            agent = db.scalar(select(Agent).where(Agent.token_hash == token_hash, Agent.status == "active"))
            if not agent:
                return JSONResponse(
                    {"error": "unauthorized", "message": "Invalid or inactive agent token"},
                    status_code=401,
                    headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
                )
            principal = AgentPrincipal(
                agent_id=agent.id,
                agent_name=agent.name,
                tenant_id=agent.tenant_id,
                environment=agent.environment,
                allowed_tools=tuple(agent.allowed_tools or []),
                allowed_purposes=tuple(agent.allowed_purposes or []),
            )
            agent.last_seen_at = datetime.now(timezone.utc)
            db.commit()
        token = current_principal.set(principal)
        try:
            return await call_next(request)
        finally:
            current_principal.reset(token)


def principal_or_error() -> AgentPrincipal:
    principal = current_principal.get()
    if principal is None:
        raise ToolError("No authenticated agent context")
    return principal


T = TypeVar("T")


def execute(
    tool_name: str,
    purpose: str,
    member_id: str | None,
    request_payload: dict[str, Any],
    operation: Callable[[AgentPrincipal], T],
) -> T:
    principal = principal_or_error()
    trace_id = str(uuid.uuid4())
    start = time.perf_counter()
    status = "success"
    decision = "allow"
    reason = "Allowed by policy"
    error_type: str | None = None
    response: Any = None
    tool = TOOLS[tool_name]
    try:
        policy = authorize(principal, tool_name, purpose)
        reason = f"{policy.policy_id}: {policy.reason}"
        response = operation(principal)
        return response
    except PolicyDenied as exc:
        status = "denied"
        decision = "deny"
        reason = f"{exc.policy_id}: {exc.reason}"
        error_type = type(exc).__name__
        raise ToolError(reason) from exc
    except ToolError:
        status = "error"
        error_type = "ToolError"
        raise
    except Exception as exc:
        status = "error"
        decision = "error"
        reason = "Unhandled tool execution error"
        error_type = type(exc).__name__
        logger.exception("Tool execution failed: %s", tool_name)
        raise ToolError("Tool execution failed") from exc
    finally:
        latency = (time.perf_counter() - start) * 1000
        try:
            request_size = len(json.dumps(request_payload, default=str))
            response_size = len(json.dumps(response, default=str)) if response is not None else 0
            with SessionLocal() as db:
                db.add(
                    AuditEvent(
                        trace_id=trace_id,
                        tenant_id=principal.tenant_id,
                        agent_id=principal.agent_id,
                        agent_name=principal.agent_name,
                        tool_name=tool_name,
                        tool_version=tool.version,
                        purpose=purpose,
                        member_ref_hash=member_hash(principal.tenant_id, member_id) if member_id else None,
                        status=status,
                        policy_decision=decision,
                        policy_reason=reason,
                        latency_ms=latency,
                        request_size=request_size,
                        response_size=response_size,
                        error_type=error_type,
                    )
                )
                db.commit()
        except Exception:
            logger.exception("Failed to write audit event")


mcp = FastMCP(
    "Enterprise Health Capability Gateway",
    stateless_http=True,
)


@mcp.tool()
def list_authorized_capabilities() -> dict[str, Any]:
    """List the tools and purposes authorized for the current enterprise agent."""
    return execute(
        "list_authorized_capabilities",
        "operational",
        None,
        {},
        lambda principal: {
            "agent": principal.agent_name,
            "tenant_id": principal.tenant_id,
            "environment": principal.environment,
            "allowed_purposes": list(principal.allowed_purposes),
            "tools": [TOOLS[name].public_dict() for name in principal.allowed_tools if name in TOOLS],
        },
    )


@mcp.tool()
def get_connection_status(member_id: str) -> dict[str, Any]:
    """Return normalized connection and synchronization status for an authorized member reference."""
    return execute(
        "get_connection_status",
        "support",
        member_id,
        {"member_id": member_id},
        lambda principal: service_get_connection_status(principal.tenant_id, member_id),
    )


@mcp.tool()
def get_member_activity_summary(member_id: str, days: int = 30) -> dict[str, Any]:
    """Return a provider-neutral activity summary with evidence, provenance and confidence."""
    if days < 7 or days > 90:
        raise ToolError("days must be between 7 and 90")
    return execute(
        "get_member_activity_summary",
        "prevention",
        member_id,
        {"member_id": member_id, "days": days},
        lambda principal: service_get_activity_summary(principal.tenant_id, member_id, days),
    )


@mcp.tool()
def assess_data_quality(member_id: str, days: int = 30) -> dict[str, Any]:
    """Assess completeness, freshness and fitness of member data for an authorized workflow."""
    if days < 7 or days > 90:
        raise ToolError("days must be between 7 and 90")
    return execute(
        "assess_data_quality",
        "prevention",
        member_id,
        {"member_id": member_id, "days": days},
        lambda principal: service_assess_data_quality(principal.tenant_id, member_id, days),
    )


@mcp.tool()
def verify_reward_eligibility(member_id: str, program_id: str = "default", days: int = 30) -> dict[str, Any]:
    """Apply deterministic reward rules and return an evidence-backed decision for human approval."""
    if days < 14 or days > 90:
        raise ToolError("days must be between 14 and 90")
    return execute(
        "verify_reward_eligibility",
        "rewards",
        member_id,
        {"member_id": member_id, "program_id": program_id, "days": days},
        lambda principal: service_verify_reward_eligibility(principal.tenant_id, member_id, program_id, days),
    )


@mcp.tool()
def prepare_prevention_brief(member_id: str, days: int = 30) -> dict[str, Any]:
    """Prepare a non-diagnostic prevention brief with evidence and safe next actions."""
    if days < 14 or days > 90:
        raise ToolError("days must be between 14 and 90")
    return execute(
        "prepare_prevention_brief",
        "prevention",
        member_id,
        {"member_id": member_id, "days": days},
        lambda principal: service_prepare_prevention_brief(principal.tenant_id, member_id, days),
    )


initialize()
app = mcp.streamable_http_app()
app.add_middleware(BearerAuthMiddleware)


if __name__ == "__main__":
    uvicorn.run(app, host=settings.mcp_host, port=settings.mcp_port, log_level=settings.log_level.lower())
