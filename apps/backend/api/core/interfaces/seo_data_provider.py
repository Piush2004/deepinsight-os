from abc import ABC, abstractmethod
from typing import Any, Dict, List
from uuid import UUID


class SEODataProvider(ABC):
    """Abstract interface for search-performance data (Search Console today; a
    real Google Search Console connector plugs into this later without the SEO
    Intelligence rules/agent above it ever changing - see docs/PROJECT_RULES.md
    Rule 6, and api/core/connectors/ for the same pattern already used for
    GA4/GSC integration data). No caller above this interface may assume
    anything about where the rows came from."""

    @abstractmethod
    def get_search_performance(self, client_id: UUID, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Returns one row per (keyword, page) pair actually observed in the
        window, each with at least: entity, entity_type ("keyword"|"page"),
        impressions, clicks, ctr, position, and the same four fields for the
        prior comparable period (impressions_previous, clicks_previous,
        ctr_previous, position_previous) so trend/momentum rules have
        something real to compare against."""
        raise NotImplementedError
