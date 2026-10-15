from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

class BaseConnector(ABC):
    """
    Abstract Base Class for all external data connectors.
    Enforces a strict interface to ensure consistency across GA4, GSC, HubSpot, etc.
    """

    def __init__(self, client_id: uuid.UUID, integration_id: uuid.UUID, db_session):
        self.client_id = client_id
        self.integration_id = integration_id
        self.db = db_session

    def _save_token(self, access_token: str, refresh_token: Optional[str], expires_at: Optional[datetime]):
        """Get-or-create/update the ConnectorToken for this integration. ConnectorToken.integration_id
        is unique, so authenticate()/refresh_token() must upsert - inserting unconditionally raises
        IntegrityError on any re-auth. Tokens are encrypted at rest via EncryptedString."""
        from api.models.integrations import ConnectorToken

        token = self.db.query(ConnectorToken).filter(
            ConnectorToken.integration_id == self.integration_id
        ).first()
        if token:
            token.access_token = access_token
            if refresh_token:
                token.refresh_token = refresh_token
            token.expires_at = expires_at
        else:
            token = ConnectorToken(
                integration_id=self.integration_id,
                client_id=self.client_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )
            self.db.add(token)
        self.db.commit()
        return token

    @abstractmethod
    def authenticate(self, auth_code: str) -> Dict[str, Any]:
        """Exchange auth code for tokens and store them."""
        pass

    @abstractmethod
    def refresh_token(self) -> str:
        """Refresh access token if expired."""
        pass

    @abstractmethod
    def sync(self) -> List[Dict[str, Any]]:
        """
        Pull raw data from the vendor API. 
        Returns a list of raw records.
        """
        pass

    @abstractmethod
    def normalize(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert raw vendor data into DeepInsight's NormalizedMetric schema.
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Verify the connection is still valid."""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Revoke tokens and clean up connection."""
        pass
