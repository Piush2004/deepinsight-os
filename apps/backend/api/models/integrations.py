from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, JSON, Boolean, Float
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from api.models.base import BaseModel
from api.models.types import EncryptedString

class Integration(BaseModel):
    __tablename__ = "integrations"

    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String, nullable=False) # e.g., 'ga4', 'gsc'
    status = Column(String, default="pending") # pending, connected, error, disconnected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class IntegrationAccount(BaseModel):
    __tablename__ = "integration_accounts"

    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(String, nullable=False) # external ID
    account_name = Column(String, nullable=False)
    property_id = Column(String) # e.g. GA4 property ID or GSC siteUrl
    is_active = Column(Boolean, default=True)

class ConnectorToken(BaseModel):
    __tablename__ = "connector_tokens"

    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, unique=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    access_token = Column(EncryptedString, nullable=False)
    refresh_token = Column(EncryptedString)
    expires_at = Column(DateTime(timezone=True))

class IntegrationSync(BaseModel):
    __tablename__ = "integration_syncs"

    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False) # running, success, failed
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    records_processed = Column(Integer, default=0)
    error_message = Column(String)

class ConnectorLog(BaseModel):
    __tablename__ = "connector_logs"

    sync_id = Column(UUID(as_uuid=True), ForeignKey("integration_syncs.id", ondelete="CASCADE"))
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(String, nullable=False) # info, warning, error
    message = Column(String, nullable=False)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class NormalizedMetric(BaseModel):
    __tablename__ = "normalized_metrics"

    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False)
    metric_type = Column(String, nullable=False) # TrafficMetric, SearchMetric
    timestamp = Column(DateTime(timezone=True), nullable=False)
    
    # Generic dimensions
    dimension_1 = Column(String) # e.g. source/medium, query
    dimension_2 = Column(String) # e.g. device, page
    
    # Generic metrics
    value_1 = Column(Float) # e.g. sessions, clicks
    value_2 = Column(Float) # e.g. conversions, impressions
    value_3 = Column(Float) # e.g. revenue, ctr
    value_4 = Column(Float) # e.g. bounce rate, avg position
    
    raw_data = Column(JSON) # Original vendor data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
