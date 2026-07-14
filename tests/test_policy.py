import pytest

from app.policy import AgentPrincipal, PolicyDenied, authorize


def principal(tools=None, purposes=None):
    return AgentPrincipal(
        agent_id="a1",
        agent_name="Agent",
        tenant_id="t1",
        environment="production",
        allowed_tools=tuple(tools or []),
        allowed_purposes=tuple(purposes or []),
    )


def test_allows_granted_tool_and_purpose():
    decision = authorize(
        principal(["get_member_activity_summary"], ["prevention"]),
        "get_member_activity_summary",
        "prevention",
    )
    assert decision.allowed


def test_denies_ungranted_tool():
    with pytest.raises(PolicyDenied):
        authorize(principal([], ["prevention"]), "get_member_activity_summary", "prevention")


def test_denies_wrong_purpose():
    with pytest.raises(PolicyDenied):
        authorize(principal(["verify_reward_eligibility"], ["prevention"]), "verify_reward_eligibility", "prevention")
