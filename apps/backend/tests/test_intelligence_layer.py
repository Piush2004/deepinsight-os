from api.services.intelligence.rule_engine import RuleEngine
from api.services.intelligence.insight_engine import InsightEngine
from api.services.intelligence.evaluation_engine import EvaluationEngine
from api.services.intelligence.engine import IntelligenceLayer


def test_ctr_doubling_is_plus_100_percent_not_plus_2():
    # The exact scenario from the spec: previous CTR = 2%, current CTR = 4%.
    # Expected: +100% relative change, NOT +2 (percentage points mislabeled as percent).
    change = RuleEngine.calculate_percentage_change(previous=0.02, current=0.04)
    assert change == 100.0


def test_percentage_decrease_is_negative():
    change = RuleEngine.calculate_percentage_change(previous=0.10, current=0.05)
    assert change == -50.0


def test_percentage_change_from_zero_previous_is_undefined_not_infinite():
    assert RuleEngine.calculate_percentage_change(previous=0, current=100) is None


def test_no_change_is_zero_percent():
    assert RuleEngine.calculate_percentage_change(previous=50, current=50) == 0.0


def test_rule_engine_surfaces_significant_trend_signal():
    engine = RuleEngine()
    signals = engine.evaluate_metrics(
        current_metrics={"ctr": 0.04},
        historical_metrics={"ctr": 0.02},
    )
    trend_signals = [s for s in signals if s["category"] == "Trend"]
    assert len(trend_signals) == 1
    assert trend_signals[0]["percentage_change"] == 100.0
    assert trend_signals[0]["metric"] == "ctr"


def test_rule_engine_ignores_insignificant_trend():
    engine = RuleEngine()
    # 5% relative move is below the 20% significance threshold - should not be reported.
    signals = engine.evaluate_metrics(
        current_metrics={"sessions": 105},
        historical_metrics={"sessions": 100},
    )
    trend_signals = [s for s in signals if s["category"] == "Trend"]
    assert trend_signals == []


def test_rule_engine_confidence_is_computed_not_hardcoded():
    engine = RuleEngine()
    signals_low_margin = engine.evaluate_metrics({"ctr": 0.031, "bounce_rate": 0.39})
    signals_high_margin = engine.evaluate_metrics({"ctr": 0.20, "bounce_rate": 0.05})
    conf_low = next(s["confidence"] for s in signals_low_margin if s["category"] == "Web")
    conf_high = next(s["confidence"] for s in signals_high_margin if s["category"] == "Web")
    assert conf_high > conf_low  # further past the threshold -> higher confidence


def test_insight_engine_carries_trend_fields_through():
    insight_engine = InsightEngine(RuleEngine())
    insights = insight_engine.generate_insights(
        metrics={"ctr": 0.04},
        knowledge_context={},
        historical_metrics={"ctr": 0.02},
    )
    trend = next(i for i in insights if i["category"] == "Trend")
    assert trend["percentage_change"] == 100.0
    assert trend["previous_value"] == 0.02
    assert trend["current_value"] == 0.04


def test_intelligence_layer_recommendations_come_from_actionable_insights():
    layer = IntelligenceLayer()
    result = layer.generate_context(
        raw_metrics={"open_rate": 0.1, "click_rate": 0.1},
        knowledge_context={},
    )
    assert len(result["insights"]) == 1
    assert result["insights"][0]["category"] == "Email"
    assert result["recommendations"] == [result["insights"][0]["business_translation"]]


def test_evaluation_engine_scores_reflect_real_input_not_constants():
    engine = EvaluationEngine()
    grounded_result = engine.evaluate(
        generated_content="Our revenue grew because of the new campaign strategy and strong engagement.",
        source_context={"kb": {"content": "revenue grew campaign strategy engagement", "sources": ["c1"]}},
    )
    empty_result = engine.evaluate(generated_content="", source_context={})

    assert grounded_result["scores"]["groundedness"] > empty_result["scores"]["groundedness"]
    assert empty_result["scores"]["completeness"] == 0


def test_evaluation_engine_flags_invented_numbers_as_hallucination_risk():
    engine = EvaluationEngine()
    source_context = {"kb": {"content": "We had 100 signups last month.", "sources": ["c1"]}}

    grounded = engine.evaluate("We had 100 signups last month.", source_context)
    fabricated = engine.evaluate("We had 5000 signups last month, a huge win.", source_context)

    assert grounded["scores"]["hallucination_risk"] == 0
    assert fabricated["scores"]["hallucination_risk"] > 0


def test_evaluation_engine_no_citations_means_zero_citation_coverage():
    engine = EvaluationEngine()
    result = engine.evaluate("Some claim with no backing.", source_context={"kb": {"content": "x", "sources": []}})
    assert result["scores"]["citation_coverage"] == 0
