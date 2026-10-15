"""
Deterministic SEO Intelligence rules. Each function takes one search-performance row
(the shape SEODataProvider.get_search_performance() returns) and either returns a
structured opportunity dict or None. No LLM call happens anywhere in this file - per
docs/PROJECT_RULES.md Rule 4 ("deterministic intelligence before generative AI") and
this phase's own mandate, the LLM is never the source of truth for whether an
opportunity exists, only for explaining one that a rule already found.

Every threshold below is a plain constant, not a magic number buried in an
expression - see the *_THRESHOLD names. Every returned opportunity carries an
`evidence` list of the exact real numbers that triggered it, so a strategist (or the
Evaluation Engine's hallucination check) can trace every claim back to real data.
"""
import math
from typing import Any, Dict, List, Optional

# Expected CTR by position band - a simplified, widely-used industry rule of thumb
# (top-3 results capture the large majority of clicks; the curve falls off fast after
# that). Used only as a *relative* benchmark for "is this CTR unusually low for where
# it ranks", not presented anywhere as a precise external fact.
def _expected_ctr_for_position(position: float) -> float:
    if position <= 3:
        return 0.10
    if position <= 10:
        return 0.03
    if position <= 20:
        return 0.01
    return 0.005


CTR_MIN_IMPRESSIONS = 1000
CTR_UNDERPERFORMANCE_RATIO = 0.5  # actual CTR must be below half the expected CTR

MOMENTUM_MIN_POSITION_IMPROVEMENT = 5.0
MOMENTUM_MIN_RELATIVE_CHANGE = 0.30  # +30% clicks or impressions
MOMENTUM_MIN_BASE_CLICKS = 10
MOMENTUM_MIN_BASE_IMPRESSIONS = 500

RISK_MIN_RELATIVE_CLICK_DECLINE = 0.20  # -20% clicks
RISK_MIN_BASE_CLICKS = 20
RISK_MIN_POSITION_DECLINE = 3.0
RISK_MIN_RELATIVE_CTR_DECLINE = 0.20


def _pct_change(current: float, previous: float) -> Optional[float]:
    if not previous:
        return None
    return (current - previous) / previous


def detect_ctr_optimization(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Rule A - High Impression / Low CTR.

    Input: impressions, ctr, position.
    Detection logic: impressions >= CTR_MIN_IMPRESSIONS AND actual CTR is below
    CTR_UNDERPERFORMANCE_RATIO (50%) of the CTR expected for that position band -
    i.e. this keyword/page is getting real search visibility but converting far
    fewer of those impressions into clicks than similarly-ranked results typically
    do, which points at the SERP snippet (title/meta/rich-result), not the ranking
    itself.
    Output: opportunity_type=CTR_OPTIMIZATION.
    Priority logic: see opportunity_detector.compute_scores - impact scales with
    impression volume and the size of the CTR gap; effort is fixed "Low" (a title/meta
    rewrite, not new content or links).
    Confidence logic: scales with impression volume (more impressions = more
    statistically meaningful CTR measurement).
    """
    impressions = row["impressions"]
    if impressions < CTR_MIN_IMPRESSIONS:
        return None
    expected = _expected_ctr_for_position(row["position"])
    if row["ctr"] >= expected * CTR_UNDERPERFORMANCE_RATIO:
        return None
    return {
        "opportunity_type": "CTR_OPTIMIZATION",
        "title": f'"{row["entity"]}" is getting real visibility but a weak click-through rate',
        "evidence": [
            f'{impressions:,} impressions at position {row["position"]:.1f}',
            f'Actual CTR {row["ctr"]*100:.2f}% vs. ~{expected*100:.1f}% typically expected at this position',
        ],
        "recommended_actions": [
            "Rewrite the page title and meta description to better match real search intent.",
            "Check whether a featured snippet, FAQ, or rich result is available to capture for this query.",
        ],
        "effort_estimate": "Low",
        "opportunity_magnitude": max(0.0, min(1.0, (expected - row["ctr"]) / expected)),
    }


def detect_page_one_opportunity(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Rule B - Position 4-10 (page one, not yet top-3).

    Input: position.
    Detection logic: 4 <= position <= 10. Deliberately skipped if
    detect_ctr_optimization() already fired for the same row (see
    opportunity_detector.py) - a below-expected CTR at this position is the more
    specific, more actionable finding, and firing both would just be two labels for
    the same underlying row.
    Output: opportunity_type=PAGE_ONE_OPTIMIZATION, priority HIGH by construction (page
    one is inherently high-value real estate).
    Priority logic: magnitude grows toward the bottom of the band (position 10 has
    more realistic room to climb within page one than position 4).
    Confidence logic: scales with impression volume, same as the CTR rule.
    """
    position = row["position"]
    if not (4 <= position <= 10):
        return None
    return {
        "opportunity_type": "PAGE_ONE_OPTIMIZATION",
        "title": f'"{row["entity"]}" is on page one but not yet in the top 3',
        "evidence": [f'Position {position:.1f}', f'{row["impressions"]:,} impressions'],
        "recommended_actions": [
            "Strengthen on-page content depth and internal links pointing at this page.",
            "Review competing page-one results for content/format gaps.",
        ],
        "effort_estimate": "Medium",
        "opportunity_magnitude": max(0.0, min(1.0, (position - 4) / 6.0)),
    }


def detect_page_two_opportunity(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Rule C - Position 11-20 (page two).

    Input: position.
    Detection logic: 11 <= position <= 20.
    Output: opportunity_type=PAGE_TWO_OPPORTUNITY.
    Priority logic: magnitude grows toward the top of the band - position 11 is "one
    push" from page one, position 20 has much further to go.
    Confidence logic: scales with impression volume.
    """
    position = row["position"]
    if not (11 <= position <= 20):
        return None
    return {
        "opportunity_type": "PAGE_TWO_OPPORTUNITY",
        "title": f'"{row["entity"]}" is on page two, close enough to page one to be worth pushing',
        "evidence": [f'Position {position:.1f}', f'{row["impressions"]:,} impressions'],
        "recommended_actions": [
            "Expand content coverage and depth for this topic.",
            "Add internal links from related, higher-authority pages.",
            "Reinforce topical relevance in headings and body content.",
        ],
        "effort_estimate": "Medium",
        "opportunity_magnitude": max(0.0, min(1.0, (20 - position) / 9.0)),
    }


def detect_momentum(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Rule D - Positive Momentum.

    Input: position vs. position_previous, clicks vs. clicks_previous, impressions vs.
    impressions_previous.
    Detection logic: fires if ANY of - position improved by >= MOMENTUM_MIN_POSITION_IMPROVEMENT,
    clicks grew by >= 30% (with a minimum base to avoid noise on tiny numbers), or
    impressions grew by >= 30% (same minimum-base guard).
    Output: opportunity_type=MOMENTUM_OPPORTUNITY. Every condition that actually
    matched is listed in evidence, not just the first one checked.
    Priority logic: magnitude scales with the size of the position swing, capped.
    Confidence logic: scales with impression volume, same base as other rules.
    """
    reasons: List[str] = []
    position_change = row["position_previous"] - row["position"]  # positive = improved
    if position_change >= MOMENTUM_MIN_POSITION_IMPROVEMENT:
        reasons.append(f'Position improved from {row["position_previous"]:.1f} to {row["position"]:.1f}')

    click_change = _pct_change(row["clicks"], row["clicks_previous"])
    if (
        click_change is not None
        and click_change >= MOMENTUM_MIN_RELATIVE_CHANGE
        and row["clicks_previous"] >= MOMENTUM_MIN_BASE_CLICKS
    ):
        reasons.append(f'Clicks grew {click_change*100:.0f}% ({row["clicks_previous"]} -> {row["clicks"]})')

    impression_change = _pct_change(row["impressions"], row["impressions_previous"])
    if (
        impression_change is not None
        and impression_change >= MOMENTUM_MIN_RELATIVE_CHANGE
        and row["impressions_previous"] >= MOMENTUM_MIN_BASE_IMPRESSIONS
    ):
        reasons.append(
            f'Impressions grew {impression_change*100:.0f}% ({row["impressions_previous"]:,} -> {row["impressions"]:,})'
        )

    if not reasons:
        return None

    return {
        "opportunity_type": "MOMENTUM_OPPORTUNITY",
        "title": f'"{row["entity"]}" is showing real positive momentum',
        "evidence": reasons,
        "recommended_actions": [
            "Prioritize this topic for further optimization while the momentum is active.",
            "Consider a related content piece or internal link push to reinforce the trend.",
        ],
        "effort_estimate": "Low",
        "opportunity_magnitude": max(0.0, min(1.0, abs(position_change) / 20.0)),
    }


def detect_performance_risk(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Rule E - Performance Decline.

    Input: clicks vs. clicks_previous, position vs. position_previous, ctr vs. ctr_previous.
    Detection logic: fires if ANY of - clicks fell by >= 20% (minimum base to avoid
    noise), position got worse by >= 3, or CTR fell by >= 20% relative.
    Output: opportunity_type=PERFORMANCE_RISK.
    Priority logic: magnitude scales with the size of the click decline (the most
    directly revenue-relevant signal of the three).
    Confidence logic: scales with impression volume, same base as other rules.
    """
    reasons: List[str] = []
    click_change = _pct_change(row["clicks"], row["clicks_previous"])
    if (
        click_change is not None
        and click_change <= -RISK_MIN_RELATIVE_CLICK_DECLINE
        and row["clicks_previous"] >= RISK_MIN_BASE_CLICKS
    ):
        reasons.append(f'Clicks fell {abs(click_change)*100:.0f}% ({row["clicks_previous"]} -> {row["clicks"]})')

    position_change = row["position"] - row["position_previous"]  # positive = worse
    if position_change >= RISK_MIN_POSITION_DECLINE:
        reasons.append(f'Position dropped from {row["position_previous"]:.1f} to {row["position"]:.1f}')

    ctr_change = _pct_change(row["ctr"], row["ctr_previous"])
    if ctr_change is not None and ctr_change <= -RISK_MIN_RELATIVE_CTR_DECLINE:
        reasons.append(f'CTR fell {abs(ctr_change)*100:.0f}% ({row["ctr_previous"]*100:.2f}% -> {row["ctr"]*100:.2f}%)')

    if not reasons:
        return None

    magnitude = abs(click_change) if click_change is not None else 0.3
    return {
        "opportunity_type": "PERFORMANCE_RISK",
        "title": f'"{row["entity"]}" is showing a real performance decline',
        "evidence": reasons,
        "recommended_actions": [
            "Investigate whether content freshness, a competitor change, or a technical issue caused this.",
            "Review recent SERP changes (new competitors, featured snippets, algorithm updates) for this query.",
        ],
        "effort_estimate": "Medium",
        "opportunity_magnitude": max(0.0, min(1.0, magnitude)),
    }


def volume_factor(impressions: int) -> float:
    """0-1, log-scaled so impact doesn't just linearly track raw impression count
    (a keyword with 100k impressions isn't 100x more important than one with 1k -
    diminishing returns, same intuition as tf-idf-style scaling elsewhere in
    information retrieval). ~100k impressions saturates to 1.0."""
    return max(0.0, min(1.0, math.log10(max(impressions, 1) + 1) / 5.0))


ALL_RULES = [
    detect_page_one_opportunity,
    detect_page_two_opportunity,
    detect_momentum,
    detect_performance_risk,
]
