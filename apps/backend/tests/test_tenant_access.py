import uuid
from unittest.mock import MagicMock

from api.core.security import user_has_client_access, assert_client_access, ADMIN_ROLE
from fastapi import HTTPException
import pytest


class FakeUser:
    def __init__(self, role="Marketing Manager", user_id=None):
        self.role = role
        self.id = user_id or uuid.uuid4()


def _db_with_membership(exists: bool):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = object() if exists else None
    return db


def test_admin_bypasses_membership_check():
    db = _db_with_membership(exists=False)
    admin = FakeUser(role=ADMIN_ROLE)
    assert user_has_client_access(db, admin, uuid.uuid4()) is True
    db.query.assert_not_called()


def test_non_admin_with_membership_allowed():
    db = _db_with_membership(exists=True)
    user = FakeUser(role="Analyst")
    assert user_has_client_access(db, user, uuid.uuid4()) is True


def test_non_admin_without_membership_denied():
    db = _db_with_membership(exists=False)
    user = FakeUser(role="Analyst")
    assert user_has_client_access(db, user, uuid.uuid4()) is False


def test_client_role_without_membership_denied():
    db = _db_with_membership(exists=False)
    user = FakeUser(role="Client")
    assert user_has_client_access(db, user, uuid.uuid4()) is False


def test_malformed_client_id_denied_not_crashed():
    db = _db_with_membership(exists=True)
    user = FakeUser(role="Analyst")
    assert user_has_client_access(db, user, "not-a-uuid") is False


def test_none_client_id_denied():
    db = _db_with_membership(exists=True)
    user = FakeUser(role="Analyst")
    assert user_has_client_access(db, user, None) is False


def test_assert_client_access_raises_404_not_403():
    db = _db_with_membership(exists=False)
    user = FakeUser(role="Analyst")
    with pytest.raises(HTTPException) as exc:
        assert_client_access(db, user, uuid.uuid4())
    assert exc.value.status_code == 404


def test_assert_client_access_passes_silently_when_authorized():
    db = _db_with_membership(exists=True)
    user = FakeUser(role="Analyst")
    assert_client_access(db, user, uuid.uuid4())  # should not raise
