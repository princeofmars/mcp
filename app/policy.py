from __future__ import annotations

from dataclasses import dataclass

from app.tool_registry import TOOLS, ToolDefinition


class PolicyDenied(Exception):
    def __init__(self, reason: str, policy_id: str = "POLICY-DEFAULT") -> None:
        super().__init__(reason)
        self.reason = reason
        self.policy_id = policy_id


@dataclass(frozen=True)
class AgentPrincipal:
    agent_id: str
    agent_name: str
    tenant_id: str
    environment: str
    allowed_tools: tuple[str, ...]
    allowed_purposes: tuple[str, ...]


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    policy_id: str
    tool: ToolDefinition
    purpose: str


def authorize(principal: AgentPrincipal, tool_name: str, purpose: str) -> PolicyDecision:
    tool = TOOLS.get(tool_name)
    if tool is None:
        raise PolicyDenied("Unknown or unregistered tool", "TOOL-REGISTRY-001")
    if tool_name != "list_authorized_capabilities" and tool_name not in principal.allowed_tools:
        raise PolicyDenied("Agent is not granted this tool", "TOOL-PERMISSION-001")
    if purpose not in tool.purposes:
        raise PolicyDenied("Requested purpose is not supported by this tool", "PURPOSE-001")
    if purpose not in principal.allowed_purposes:
        raise PolicyDenied("Agent is not granted the requested purpose", "PURPOSE-002")
    if principal.environment not in {"development", "staging", "production"}:
        raise PolicyDenied("Unapproved agent environment", "ENVIRONMENT-001")
    return PolicyDecision(True, "Allowed by tool and purpose policy", "ALLOW-001", tool, purpose)
