"""Regression test for a real bug found during dev/demo-mode live HTTP testing
(docs/DEV_DEMO_MODE.md): BaseRepository.get()/remove() filtered Model.id (a
postgresql.UUID column) against whatever id value the caller passed - which works
transparently against a real Postgres server, but raises
`AttributeError: 'str' object has no attribute 'hex'` against SQLite whenever a router
passes a raw string id (e.g. api/routers/clients.py's client_id: str path param, which
FastAPI does not auto-convert to UUID the way a `client_id: UUID` annotation would).

This specifically broke GET /clients/{client_id} for any authorized non-admin user (an
unauthorized request never reached this code - assert_client_access() 404s first, which
is exactly why this was missed even after fixing the same bug class in
api/services/knowledge/retrieval.py and api/core/tasks.py).

Hermetic: in-memory SQLite, no Postgres.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.models.base import Base
import api.models  # noqa: F401 - registers every model on Base.metadata
from api.models.client import Client
from api.repositories.client_repository import client_repository


def test_get_by_string_id_works_against_sqlite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    client = Client(name="Repo Compat Test Client")
    db.add(client)
    db.commit()

    # The exact bug: a plain string id, matching what a str-typed FastAPI path param
    # actually delivers (not a real uuid.UUID instance).
    fetched = client_repository.get(db, id=str(client.id))

    assert fetched is not None
    assert fetched.id == client.id
    db.close()


def test_get_by_malformed_string_id_returns_none_not_a_crash():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    result = client_repository.get(db, id="not-a-real-uuid")

    assert result is None
    db.close()


def test_remove_by_string_id_works_against_sqlite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    client = Client(name="Repo Compat Delete Test Client")
    db.add(client)
    db.commit()
    client_id = client.id

    removed = client_repository.remove(db, id=str(client_id))

    assert removed is not None
    assert removed.is_deleted is True
    db.close()
