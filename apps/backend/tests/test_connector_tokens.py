import uuid
from datetime import datetime
from unittest.mock import MagicMock

from api.models.types import EncryptedString
from api.core.connectors.base import BaseConnector


def test_encrypted_string_round_trips_and_is_not_plaintext_on_the_wire():
    field = EncryptedString()
    plaintext = "super-secret-oauth-token"
    ciphertext = field.process_bind_param(plaintext, dialect=None)

    assert ciphertext != plaintext
    assert plaintext not in ciphertext

    decrypted = field.process_result_value(ciphertext, dialect=None)
    assert decrypted == plaintext


def test_encrypted_string_passes_through_none():
    field = EncryptedString()
    assert field.process_bind_param(None, dialect=None) is None
    assert field.process_result_value(None, dialect=None) is None


class DummyConnector(BaseConnector):
    def authenticate(self, auth_code): pass
    def refresh_token(self): pass
    def sync(self): return []
    def normalize(self, raw_data): return []
    def validate(self): return True
    def disconnect(self): return True


def _connector_with_mock_db(existing_token=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing_token
    connector = DummyConnector(client_id=uuid.uuid4(), integration_id=uuid.uuid4(), db_session=db)
    return connector, db


def test_save_token_inserts_when_none_exists():
    connector, db = _connector_with_mock_db(existing_token=None)
    connector._save_token("access-1", "refresh-1", datetime.utcnow())

    assert db.add.called, "a new ConnectorToken should be added when none exists"
    db.commit.assert_called_once()


def test_save_token_updates_in_place_when_one_exists_no_duplicate_insert():
    existing = MagicMock(access_token="old-access", refresh_token="old-refresh")
    connector, db = _connector_with_mock_db(existing_token=existing)

    connector._save_token("new-access", "new-refresh", datetime.utcnow())

    db.add.assert_not_called()  # must not attempt a second INSERT against the unique integration_id
    assert existing.access_token == "new-access"
    assert existing.refresh_token == "new-refresh"
    db.commit.assert_called_once()


def test_save_token_refresh_keeps_existing_refresh_token_when_not_rotated():
    existing = MagicMock(access_token="old-access", refresh_token="old-refresh")
    connector, db = _connector_with_mock_db(existing_token=existing)

    connector._save_token("rotated-access", None, datetime.utcnow())

    assert existing.access_token == "rotated-access"
    assert existing.refresh_token == "old-refresh"  # untouched since provider didn't rotate it
