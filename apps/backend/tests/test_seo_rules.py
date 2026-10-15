"""Unit tests for the deterministic SEO rules (api/services/seo/rules.py) and the
opportunity detector/scoring (api/services/seo/opportunity_detector.py). No LLM, no
mocks of the rules themselves - these test the real deterministic logic directly."""
from api.services.seo import rules
from api.services.seo.opportunity_detector import detect_opportunities


def _row(**overrides):
    base = {
        "entity": "test keyword",
        "entity_type": "keyword",
        "page": "/test",
        "impressions": 5000,
        "clicks": 150,
        "ctr": 0.03,
        "position": 15.0,
        "impressions_previous": 5000,
        "clicks_previous": 150,
        "ctr_previous": 0.03,
        "position_previous": 15.0,
    }
    base.update(overrides)
    return base


def test_ctr_optimization_fires_on_high_impressions_low_ctr_strong_position():
    row = _row(impressions=18000, position=6.2, ctr=0.011)
    result = rules.detect_ctr_optimization(row)
    assert result is not None
    assert result["opportunity_type"] == "CTR_OPTIMIZATION"
    assert "1.10%" in result["evidence"][1]


def test_ctr_optimization_does_not_fire_below_impression_threshold():
    row = _row(impressions=500, position=6.2, ctr=0.005)  # would otherwise qualify
    assert rules.detect_ctr_optimization(row) is None


def test_ctr_optimization_does_not_fire_when_ctr_is_reasonable_for_position():
    row = _row(impressions=18000, position=6.2, ctr=0.035)  # above expected 3% for this band
    assert rules.detect_ctr_optimization(row) is None


def test_page_one_opportunity_fires_for_position_4_to_10():
    for position in (4.0, 6.5, 10.0):
        result = rules.detect_page_one_opportunity(_row(position=position))
        assert result is not None, f"expected a hit at position {position}"
        assert result["opportunity_type"] == "PAGE_ONE_OPTIMIZATION"


def test_page_one_opportunity_does_not_fire_outside_band():
    assert rules.detect_page_one_opportunity(_row(position=3.9)) is None
    assert rules.detect_page_one_opportunity(_row(position=10.1)) is None


def test_page_two_opportunity_fires_for_position_11_to_20():
    for position in (11.0, 15.0, 20.0):
        result = rules.detect_page_two_opportunity(_row(position=position))
        assert result is not None, f"expected a hit at position {position}"
        assert result["opportunity_type"] == "PAGE_TWO_OPPORTUNITY"


def test_page_two_opportunity_does_not_fire_outside_band():
    assert rules.detect_page_two_opportunity(_row(position=10.9)) is None
    assert rules.detect_page_two_opportunity(_row(position=20.1)) is None


def test_momentum_fires_on_position_improvement():
    row = _row(position=11.0, position_previous=22.0, clicks=150, clicks_previous=150,
                impressions=5000, impressions_previous=5000)
    result = rules.detect_momentum(row)
    assert result is not None
    assert "Position improved" in result["evidence"][0]


def test_momentum_fires_on_click_growth_alone():
    row = _row(position=15.0, position_previous=15.2, clicks=200, clicks_previous=100,
                impressions=5000, impressions_previous=5000)
    result = rules.detect_momentum(row)
    assert result is not None
    assert any("Clicks grew" in e for e in result["evidence"])


def test_momentum_ignores_click_growth_below_base_threshold():
    """A jump from 2 clicks to 5 clicks is +150% but statistical noise, not momentum -
    the minimum-base guard exists specifically to suppress this."""
    row = _row(position=15.0, position_previous=15.1, clicks=5, clicks_previous=2,
                impressions=5000, impressions_previous=5000)
    assert rules.detect_momentum(row) is None


def test_momentum_does_not_fire_on_flat_performance():
    assert rules.detect_momentum(_row()) is None


def test_performance_risk_fires_on_click_decline():
    row = _row(clicks=118, clicks_previous=169, position=9.8, position_previous=8.1,
                ctr=0.0095, ctr_previous=0.014)
    result = rules.detect_performance_risk(row)
    assert result is not None
    assert any("Clicks fell" in e for e in result["evidence"])


def test_performance_risk_does_not_fire_on_flat_performance():
    assert rules.detect_performance_risk(_row()) is None


def test_performance_risk_ignores_click_decline_below_base_threshold():
    row = _row(clicks=3, clicks_previous=10, position=15.0, position_previous=15.0,
                ctr=0.03, ctr_previous=0.03)  # -70% but base too small to trust
    assert rules.detect_performance_risk(row) is None


def test_priority_confidence_scoring_is_deterministic_and_bounded():
    # Every *_previous field held equal to its current value so only the CTR rule
    # fires - isolates the scoring assertion from the trend rules, which are tested
    # separately above.
    row = _row(impressions=18000, impressions_previous=18000, position=6.2, position_previous=6.2,
               ctr=0.011, ctr_previous=0.011, clicks=198, clicks_previous=198)
    opportunities = detect_opportunities([row])
    assert len(opportunities) == 1
    opp = opportunities[0]
    assert 0 <= opp["priority_score"] <= 100
    assert 0 <= opp["confidence_score"] <= 100
    assert 0 <= opp["impact_score"] <= 100
    assert opp["effort_estimate"] in ("Low", "Medium", "High")
    # Same input must always produce the same scores - no randomness anywhere.
    opportunities_again = detect_opportunities([row])
    assert opportunities_again[0]["priority_score"] == opp["priority_score"]
    assert opportunities_again[0]["confidence_score"] == opp["confidence_score"]


def test_ctr_optimization_suppresses_redundant_positional_rule_on_same_row():
    """A row that satisfies both the CTR rule and the page-one positional band should
    only produce the more specific CTR_OPTIMIZATION finding, not both - see
    opportunity_detector.detect_opportunities' cascade logic."""
    row = _row(impressions=18000, impressions_previous=18000, position=6.2, position_previous=6.2,
               ctr=0.011, ctr_previous=0.011, clicks=198, clicks_previous=198)  # qualifies for both bands, flat trend
    opportunities = detect_opportunities([row])
    types = [o["opportunity_type"] for o in opportunities]
    assert types == ["CTR_OPTIMIZATION"]


def test_a_healthy_keyword_produces_zero_opportunities():
    """Proves the rules don't just rubber-stamp everything - a keyword with a strong
    position, strong CTR, and flat trend should trigger nothing."""
    row = _row(position=1.4, ctr=0.30, ctr_previous=0.30, position_previous=1.5,
                clicks=660, clicks_previous=630, impressions=2200, impressions_previous=2100)
    assert detect_opportunities([row]) == []


def test_opportunities_are_sorted_by_priority_descending():
    rows = [
        _row(entity="low", impressions=1000, position=19.0),  # weak page-two signal
        _row(entity="high", impressions=18000, position=6.2, ctr=0.011),  # strong CTR opportunity
    ]
    opportunities = detect_opportunities(rows)
    scores = [o["priority_score"] for o in opportunities]
    assert scores == sorted(scores, reverse=True)


def test_category_bucketing_matches_frontend_contract():
    ctr_opps = detect_opportunities([_row(impressions=18000, impressions_previous=18000, position=6.2,
                                           position_previous=6.2, ctr=0.011, ctr_previous=0.011,
                                           clicks=198, clicks_previous=198)])
    assert len(ctr_opps) == 1
    assert ctr_opps[0]["category"] == "QUICK_WIN"  # CTR fix is Low effort

    # position held outside every positional band (25.0) so only the click-decline
    # risk signal fires, isolating this assertion from PAGE_ONE_OPTIMIZATION also
    # firing for the same row and potentially outranking it by priority_score.
    risk_opps = detect_opportunities([_row(clicks=118, clicks_previous=169, position=25.0, position_previous=25.0, ctr=0.05, ctr_previous=0.07)])
    assert len(risk_opps) == 1
    assert risk_opps[0]["category"] == "PERFORMANCE_RISK"

    # position=11.0 also lands in the page-two band, so this row legitimately produces
    # two independent opportunities (a real trend signal AND a real static-position
    # signal) - look up the momentum one specifically rather than assume ordering.
    all_opps = detect_opportunities([_row(position=11.0, position_previous=22.0)])
    momentum_hits = [o for o in all_opps if o["opportunity_type"] == "MOMENTUM_OPPORTUNITY"]
    assert len(momentum_hits) == 1
    assert momentum_hits[0]["category"] == "EMERGING_MOMENTUM"
