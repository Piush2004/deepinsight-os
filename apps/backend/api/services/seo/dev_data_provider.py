"""
Development/demo SEODataProvider - deterministic search-performance fixtures, isolated
from any production provider logic (see docs/DEV_DEMO_MODE.md for the same principle
already applied to VECTOR_STORE_PROVIDER/AUTH_MODE). Selected via
SEO_DATA_PROVIDER=dev (the only implementation that currently exists - a real Google
Search Console connector is future work per docs/ROADMAP.md, and plugs in behind the
exact same SEODataProvider interface without any rule/agent code changing).

Every row here is realistic and clearly fictional (fictional client, generic marketing
keywords) - never presented to a user as real client data. Each scenario is chosen
specifically to exercise a different deterministic rule in api/services/seo/rules.py,
not to look good in a screenshot.
"""
from typing import Any, Dict, List
from uuid import UUID

from api.core.interfaces.seo_data_provider import SEODataProvider

# Same client_id for every call, deliberately - this is fixture data, not a real
# per-client dataset, and the SEOAgent explicitly labels it as such in its output
# (see api/core/agent/seo_agent.py). Position values use one decimal place, matching
# how Search Console itself reports average position.
_FIXTURE_ROWS: List[Dict[str, Any]] = [
    {
        # Scenario 1 - Quick Win: strong position, high impressions, weak CTR.
        "entity": "enterprise ai marketing",
        "entity_type": "keyword",
        "page": "/solutions/enterprise-ai-marketing",
        "impressions": 18000,
        "clicks": 198,
        "ctr": 0.011,
        "position": 6.2,
        "impressions_previous": 17200,
        "clicks_previous": 189,
        "ctr_previous": 0.011,
        "position_previous": 6.5,
    },
    {
        # Scenario 2 - Page Two Opportunity: meaningful volume, position 11-20.
        "entity": "ai content strategy",
        "entity_type": "keyword",
        "page": "/blog/ai-content-strategy",
        "impressions": 9000,
        "clicks": 72,
        "ctr": 0.008,
        "position": 14.3,
        "impressions_previous": 8600,
        "clicks_previous": 70,
        "ctr_previous": 0.0081,
        "position_previous": 14.6,
    },
    {
        # Scenario 3 - Positive Momentum: large real position improvement.
        "entity": "marketing intelligence platform",
        "entity_type": "keyword",
        "page": "/platform",
        "impressions": 5400,
        "clicks": 162,
        "ctr": 0.03,
        "position": 11.0,
        "impressions_previous": 3100,
        "clicks_previous": 46,
        "ctr_previous": 0.0148,
        "position_previous": 22.0,
    },
    {
        # Scenario 4 - Performance Decline: clicks down sharply, impressions stable.
        "entity": "marketing automation software",
        "entity_type": "page",
        "page": "/products/marketing-automation",
        "impressions": 12400,
        "clicks": 118,
        "ctr": 0.0095,
        "position": 9.8,
        "impressions_previous": 12100,
        "clicks_previous": 169,
        "ctr_previous": 0.014,
        "position_previous": 8.1,
    },
    {
        # Page-one, already-strong performer - included so the rule set proves it does
        # NOT flag a keyword that doesn't need attention (no opportunity should fire).
        "entity": "deepinsight os",
        "entity_type": "keyword",
        "page": "/",
        "impressions": 2200,
        "clicks": 660,
        "ctr": 0.30,
        "position": 1.4,
        "impressions_previous": 2100,
        "clicks_previous": 630,
        "ctr_previous": 0.30,
        "position_previous": 1.5,
    },
    {
        # Additional page-one (4-10) candidate with weaker CTR than its position
        # deserves, but not low enough to double-fire the CTR rule - exercises the
        # PAGE_ONE_OPTIMIZATION rule on its own.
        "entity": "agency reporting software",
        "entity_type": "keyword",
        "page": "/solutions/agency-reporting",
        "impressions": 4100,
        "clicks": 156,
        "ctr": 0.038,
        "position": 8.4,
        "impressions_previous": 3950,
        "clicks_previous": 148,
        "ctr_previous": 0.0375,
        "position_previous": 8.6,
    },
]


class DevSEODataProvider(SEODataProvider):
    """Real implementation of SEODataProvider - deterministic fixture rows, not a
    stub. Selected via api/services/seo/provider_factory.py, the same
    configuration-driven pattern as get_embedding_provider()/get_vector_store()."""

    def get_search_performance(self, client_id: UUID, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        return [dict(row) for row in _FIXTURE_ROWS]
