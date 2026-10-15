from api.core.config import settings
from api.core.interfaces.seo_data_provider import SEODataProvider
from api.services.seo.dev_data_provider import DevSEODataProvider


def get_seo_data_provider() -> SEODataProvider:
    """Selects the concrete SEODataProvider via SEO_DATA_PROVIDER - 'dev' (default,
    the only implementation that exists today) or 'google_search_console' (future
    work, not built this session per docs/ROADMAP.md - live GSC OAuth/credentials are
    out of scope, see docs/PROJECT_RULES.md Rule 6). Every caller (the SEOAgent, and
    only the SEOAgent) goes through this factory rather than importing a concrete
    provider directly, so swapping in the real connector later touches this one
    function, not the rules/agent/API layers above it."""
    provider = settings.SEO_DATA_PROVIDER
    if provider == "dev":
        return DevSEODataProvider()
    raise NotImplementedError(
        f"SEO_DATA_PROVIDER={provider!r} is not implemented. Only 'dev' exists today - "
        "a real Google Search Console provider is future work (docs/ROADMAP.md)."
    )
