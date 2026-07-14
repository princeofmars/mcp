from __future__ import annotations

from typing import Any

from app.connectors import DemoHealthProvider


provider = DemoHealthProvider()


def get_connection_status(tenant_id: str, member_id: str) -> dict[str, Any]:
    result = provider.connection_status(tenant_id, member_id)
    return {
        **result,
        "member_reference": member_id,
        "permitted_next_actions": ["prepare_reconnection_guidance"] if not result["connected"] else [],
    }


def get_activity_summary(tenant_id: str, member_id: str, days: int) -> dict[str, Any]:
    result = provider.activity_summary(tenant_id, member_id, days)
    confidence = min(0.99, max(0.2, result["coverage"] * 0.95))
    return {
        "member_reference": member_id,
        "summary": {k: result[k] for k in ["period_days", "average_daily_steps", "trend_percent", "trend", "usable_days", "missing_days"]},
        "evidence": {
            "source": result["source"],
            "coverage": result["coverage"],
            "daily": result["daily"],
        },
        "confidence": round(confidence, 3),
        "interpretation": {"type": "behavioural_observation", "diagnostic": False},
        "synthetic": result["synthetic"],
    }


def assess_data_quality(tenant_id: str, member_id: str, days: int) -> dict[str, Any]:
    result = provider.data_quality(tenant_id, member_id, days)
    result["member_reference"] = member_id
    result["recommended_action"] = "continue_data_collection" if result["status"] == "insufficient" else "proceed_with_authorized_workflow"
    return result


def verify_reward_eligibility(tenant_id: str, member_id: str, program_id: str, days: int) -> dict[str, Any]:
    activity = provider.activity_summary(tenant_id, member_id, days)
    quality = provider.data_quality(tenant_id, member_id, days)
    minimum_steps = 7000
    minimum_usable_days = max(14, int(days * 0.7))
    eligible = (
        quality["fit_for_rewards"]
        and activity["average_daily_steps"] >= minimum_steps
        and activity["usable_days"] >= minimum_usable_days
    )
    reasons = []
    if not quality["fit_for_rewards"]:
        reasons.append("Data quality is insufficient for reward verification")
    if activity["average_daily_steps"] < minimum_steps:
        reasons.append(f"Average daily steps are below {minimum_steps}")
    if activity["usable_days"] < minimum_usable_days:
        reasons.append(f"Fewer than {minimum_usable_days} usable days")
    return {
        "member_reference": member_id,
        "program_id": program_id,
        "decision": "eligible" if eligible else "not_eligible",
        "requires_human_approval": True,
        "rule_version": "reward-default-1.0.0",
        "evidence": {
            "average_daily_steps": activity["average_daily_steps"],
            "usable_days": activity["usable_days"],
            "coverage": activity["coverage"],
            "quality_score": quality["quality_score"],
        },
        "reasons": reasons or ["All deterministic eligibility criteria were met"],
        "synthetic": True,
    }


def prepare_prevention_brief(tenant_id: str, member_id: str, days: int) -> dict[str, Any]:
    activity = provider.activity_summary(tenant_id, member_id, days)
    quality = provider.data_quality(tenant_id, member_id, days)
    if quality["status"] == "insufficient":
        return {
            "member_reference": member_id,
            "status": "insufficient_evidence",
            "reason": quality["limitations"][0],
            "recommended_action": "continue_data_collection",
            "requires_human_review": True,
            "diagnostic": False,
            "synthetic": True,
        }
    narrative = (
        f"Activity is {activity['trend']} over the previous {days} days, with an average of "
        f"{activity['average_daily_steps']} daily steps and {activity['coverage']:.0%} data coverage."
    )
    actions = ["review_with_prevention_professional"]
    if activity["trend"] == "declining":
        actions.append("consider_voluntary_activity_support")
    return {
        "member_reference": member_id,
        "status": "ready_for_review",
        "brief": narrative,
        "confidence": round(quality["quality_score"], 3),
        "evidence": {
            "average_daily_steps": activity["average_daily_steps"],
            "trend_percent": activity["trend_percent"],
            "coverage": activity["coverage"],
            "source": activity["source"],
        },
        "permitted_next_actions": actions,
        "prohibited_actions": ["make_diagnosis", "modify_premium", "deny_claim"],
        "requires_human_review": True,
        "diagnostic": False,
        "synthetic": True,
    }
