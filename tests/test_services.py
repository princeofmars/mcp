from app.services import assess_data_quality, get_activity_summary, prepare_prevention_brief, verify_reward_eligibility


def test_demo_results_are_deterministic():
    first = get_activity_summary("tenant", "member", 30)
    second = get_activity_summary("tenant", "member", 30)
    assert first == second


def test_quality_has_sufficiency_state():
    result = assess_data_quality("tenant", "member", 30)
    assert result["status"] in {"sufficient", "insufficient"}
    assert 0 <= result["quality_score"] <= 1


def test_reward_is_deterministic_and_human_reviewed():
    result = verify_reward_eligibility("tenant", "member", "p1", 30)
    assert result["decision"] in {"eligible", "not_eligible"}
    assert result["requires_human_approval"] is True


def test_prevention_brief_is_non_diagnostic():
    result = prepare_prevention_brief("tenant", "member", 30)
    assert result["diagnostic"] is False
