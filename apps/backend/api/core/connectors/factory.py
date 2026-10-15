from api.core.connectors.ga4 import GA4Connector
from api.core.connectors.gsc import GSCConnector
from api.core.connectors.base import BaseConnector
import uuid

def get_connector(provider: str, client_id: uuid.UUID, integration_id: uuid.UUID, db_session) -> BaseConnector:
    if provider == "ga4":
        return GA4Connector(client_id=client_id, integration_id=integration_id, db_session=db_session)
    elif provider == "gsc":
        return GSCConnector(client_id=client_id, integration_id=integration_id, db_session=db_session)
    else:
        raise ValueError(f"Unknown integration provider: {provider}")
