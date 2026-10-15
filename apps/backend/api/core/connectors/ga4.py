from typing import Dict, Any, List
from api.core.connectors.base import BaseConnector
from api.models.integrations import ConnectorToken
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GA4Connector(BaseConnector):
    """
    Google Analytics 4 Connector.
    Mocks actual OAuth and API calls for Phase 4 proof-of-concept, 
    but strictly follows the requested architecture.
    """
    
    def authenticate(self, auth_code: str) -> Dict[str, Any]:
        # NOTE: this is still a mocked OAuth exchange (no real Google API client wired
        # up yet) - see docs/CLAUDE_CODE_AUDIT.md. What IS real now: upsert-safe token
        # storage, encrypted at rest via ConnectorToken.access_token/refresh_token
        # (EncryptedString, api/models/types.py).
        logger.info(f"Authenticating GA4 with code {auth_code}")
        self._save_token(
            access_token="mock_ga4_access_token",
            refresh_token="mock_ga4_refresh_token",
            expires_at=datetime.utcnow(),
        )
        return {"status": "success", "provider": "ga4"}

    def refresh_token(self) -> str:
        logger.info(f"Refreshing GA4 token for {self.integration_id}")
        new_access_token = "new_mock_access_token"
        self._save_token(access_token=new_access_token, refresh_token=None, expires_at=datetime.utcnow())
        return new_access_token

    def sync(self) -> List[Dict[str, Any]]:
        logger.info(f"Syncing GA4 data for {self.integration_id}")
        # Mock API response returning raw GA4 records
        return [
            {
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "sourceMedium": "google / organic",
                "deviceCategory": "mobile",
                "sessions": 1500,
                "conversions": 45,
                "revenue": 12500.00,
                "bounceRate": 0.45
            },
            {
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "sourceMedium": "direct / none",
                "deviceCategory": "desktop",
                "sessions": 800,
                "conversions": 12,
                "revenue": 3400.00,
                "bounceRate": 0.30
            }
        ]

    def normalize(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        logger.info(f"Normalizing GA4 data for {self.integration_id}")
        normalized = []
        for row in raw_data:
            normalized.append({
                "client_id": self.client_id,
                "integration_id": self.integration_id,
                "metric_type": "TrafficMetric",
                "timestamp": datetime.strptime(row["date"], "%Y-%m-%d"),
                "dimension_1": row.get("sourceMedium"),
                "dimension_2": row.get("deviceCategory"),
                "value_1": row.get("sessions"), # Sessions
                "value_2": row.get("conversions"), # Conversions
                "value_3": row.get("revenue"), # Revenue
                "value_4": row.get("bounceRate"), # Bounce Rate
                "raw_data": row
            })
        return normalized

    def validate(self) -> bool:
        return True

    def disconnect(self) -> bool:
        logger.info(f"Disconnecting GA4 for {self.integration_id}")
        # Clean up tokens
        self.db.query(ConnectorToken).filter_by(integration_id=self.integration_id).delete()
        self.db.commit()
        return True
