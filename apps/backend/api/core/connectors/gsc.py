from typing import Dict, Any, List
from api.core.connectors.base import BaseConnector
from api.models.integrations import ConnectorToken
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GSCConnector(BaseConnector):
    """
    Google Search Console Connector.
    Mocks actual OAuth and API calls for Phase 4 proof-of-concept.
    """
    
    def authenticate(self, auth_code: str) -> Dict[str, Any]:
        # NOTE: still a mocked OAuth exchange - see docs/CLAUDE_CODE_AUDIT.md. What IS
        # real now: upsert-safe token storage, encrypted at rest via ConnectorToken
        # (EncryptedString, api/models/types.py).
        logger.info(f"Authenticating GSC with code {auth_code}")
        self._save_token(
            access_token="mock_gsc_access_token",
            refresh_token="mock_gsc_refresh_token",
            expires_at=datetime.utcnow(),
        )
        return {"status": "success", "provider": "gsc"}

    def refresh_token(self) -> str:
        logger.info(f"Refreshing GSC token for {self.integration_id}")
        new_access_token = "new_mock_gsc_access_token"
        self._save_token(access_token=new_access_token, refresh_token=None, expires_at=datetime.utcnow())
        return new_access_token

    def sync(self) -> List[Dict[str, Any]]:
        logger.info(f"Syncing GSC data for {self.integration_id}")
        return [
            {
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "query": "joseph studios marketing",
                "page": "https://josephstudios.net/",
                "clicks": 450,
                "impressions": 5000,
                "ctr": 0.09,
                "position": 1.2
            },
            {
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "query": "b2b ai marketing",
                "page": "https://josephstudios.net/b2b-ai",
                "clicks": 120,
                "impressions": 3000,
                "ctr": 0.04,
                "position": 4.5
            }
        ]

    def normalize(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        logger.info(f"Normalizing GSC data for {self.integration_id}")
        normalized = []
        for row in raw_data:
            normalized.append({
                "client_id": self.client_id,
                "integration_id": self.integration_id,
                "metric_type": "SearchMetric",
                "timestamp": datetime.strptime(row["date"], "%Y-%m-%d"),
                "dimension_1": row.get("query"),
                "dimension_2": row.get("page"),
                "value_1": row.get("clicks"), # Clicks
                "value_2": row.get("impressions"), # Impressions
                "value_3": row.get("ctr"), # CTR
                "value_4": row.get("position"), # Avg Position
                "raw_data": row
            })
        return normalized

    def validate(self) -> bool:
        return True

    def disconnect(self) -> bool:
        logger.info(f"Disconnecting GSC for {self.integration_id}")
        self.db.query(ConnectorToken).filter_by(integration_id=self.integration_id).delete()
        self.db.commit()
        return True
