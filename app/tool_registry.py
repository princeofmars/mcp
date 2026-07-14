from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    title: str
    version: str
    description: str
    risk_level: int
    read_only: bool
    purposes: tuple[str, ...]
    requires_member: bool = True
    human_approval: bool = False

    def public_dict(self) -> dict:
        value = asdict(self)
        value["purposes"] = list(self.purposes)
        return value


TOOLS: dict[str, ToolDefinition] = {
    "list_authorized_capabilities": ToolDefinition(
        name="list_authorized_capabilities",
        title="List authorized capabilities",
        version="1.0.0",
        description="Returns the tools and purposes granted to the current enterprise agent.",
        risk_level=0,
        read_only=True,
        purposes=("operational",),
        requires_member=False,
    ),
    "get_connection_status": ToolDefinition(
        name="get_connection_status",
        title="Get device connection status",
        version="1.0.0",
        description="Returns normalized device connection and synchronization status.",
        risk_level=1,
        read_only=True,
        purposes=("support", "prevention"),
    ),
    "get_member_activity_summary": ToolDefinition(
        name="get_member_activity_summary",
        title="Get member activity summary",
        version="1.0.0",
        description="Returns a provider-neutral activity summary with provenance and confidence.",
        risk_level=1,
        read_only=True,
        purposes=("prevention", "rewards"),
    ),
    "assess_data_quality": ToolDefinition(
        name="assess_data_quality",
        title="Assess health data quality",
        version="1.0.0",
        description="Evaluates completeness, freshness and fitness for the requested purpose.",
        risk_level=1,
        read_only=True,
        purposes=("support", "prevention", "rewards"),
    ),
    "verify_reward_eligibility": ToolDefinition(
        name="verify_reward_eligibility",
        title="Verify reward eligibility",
        version="1.0.0",
        description="Applies deterministic program rules and returns evidence for a reward decision.",
        risk_level=2,
        read_only=True,
        purposes=("rewards",),
        human_approval=True,
    ),
    "prepare_prevention_brief": ToolDefinition(
        name="prepare_prevention_brief",
        title="Prepare prevention brief",
        version="1.0.0",
        description="Creates a non-diagnostic, evidence-backed summary for a prevention professional.",
        risk_level=2,
        read_only=True,
        purposes=("prevention",),
        human_approval=True,
    ),
}

DEFAULT_AGENT_TOOLS = list(TOOLS.keys())
DEFAULT_PURPOSES = ["operational", "support", "prevention", "rewards"]
