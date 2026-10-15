"""
Development/demo seed script for DeepInsight OS.

Populates a local dev database (SQLite by default, see docs/DEV_DEMO_MODE.md) with a
demo agency, demo users, demo clients, and client memberships - all real rows in the
real schema, not fabricated fixtures baked into the frontend. This is explicitly
dev/demo-only data, clearly labeled as such, never run against a production database
(see the safety check below).

IMPORTANT - run this BEFORE starting the API server, not against one that's already
running: when VECTOR_STORE_PROVIDER=memory (the dev/demo default), the vector store is
process-local. Documents/reports/content need to be created THROUGH the running
server's own process (via its real HTTP API) to land in the same in-memory store that
process will query later - a separate script process populating its own copy would be
invisible to the server. This script therefore only seeds what's safe to create
out-of-process (everything persisted to SQLite, which is a real shared file): users,
clients, memberships. Upload documents and generate reports/content through the
running app itself (the frontend, or scripts/demo_http_walkthrough.py) after starting
the server.

Usage (from apps/backend, with the dev/demo env vars exported - see
docs/DEV_DEMO_MODE.md):

    python -m scripts.seed_demo
"""
import sys

from api.core.config import settings
from api.database.session import engine, SessionLocal, Base
import api.models  # noqa: F401 - registers every model on Base.metadata
from api.models.user import User
from api.models.client import Client
from api.models.membership import ClientMembership

DEMO_ADMIN_CLERK_ID = "demo-admin"
DEMO_MANAGER_CLERK_ID = "demo-manager"

DEMO_CLIENTS = [
    {
        "name": "Aurora Wellness Collective",
        "industry": "Health & Wellness",
        "website": "https://aurorawellness.example",
        "description": "A boutique wellness studio chain expanding into digital-first client acquisition.",
    },
    {
        "name": "Northstar Legal Partners",
        "industry": "Professional Services",
        "website": "https://northstarlegal.example",
        "description": "A regional law firm building thought-leadership content and organic search authority.",
    },
    {
        "name": "Fernway Outdoor Supply",
        "industry": "E-Commerce / Retail",
        "website": "https://fernwayoutdoor.example",
        "description": "A DTC outdoor gear brand focused on retention marketing and content-driven SEO.",
    },
]


def _safety_check():
    if settings.ENVIRONMENT == "production":
        print("Refusing to seed demo data: ENVIRONMENT=production.", file=sys.stderr)
        sys.exit(1)


def _create_schema():
    Base.metadata.create_all(bind=engine)
    print(f"Schema ready ({engine.url}).")


def _get_or_create_user(db, clerk_id, email, role, first_name, last_name):
    user = db.query(User).filter(User.clerk_id == clerk_id).first()
    if user:
        return user
    user = User(clerk_id=clerk_id, email=email, role=role, first_name=first_name, last_name=last_name)
    db.add(user)
    db.flush()
    return user


def _get_or_create_client(db, name, industry, website, description):
    client = db.query(Client).filter(Client.name == name).first()
    if client:
        return client
    client = Client(name=name, industry=industry, website=website, description=description)
    db.add(client)
    db.flush()
    return client


def _ensure_membership(db, user, client):
    existing = (
        db.query(ClientMembership)
        .filter(ClientMembership.user_id == user.id, ClientMembership.client_id == client.id)
        .first()
    )
    if existing:
        return
    db.add(ClientMembership(user_id=user.id, client_id=client.id))


def main():
    _safety_check()
    _create_schema()

    db = SessionLocal()
    try:
        admin = _get_or_create_user(db, DEMO_ADMIN_CLERK_ID, "admin@demo.deepinsight.local", "Admin", "Demo", "Admin")
        manager = _get_or_create_user(db, DEMO_MANAGER_CLERK_ID, "manager@demo.deepinsight.local", "Marketing Manager", "Demo", "Manager")
        db.flush()
        print(f"Users: admin={admin.id} manager={manager.id}")

        clients = [_get_or_create_client(db, **c) for c in DEMO_CLIENTS]
        db.flush()
        for c in clients:
            print(f"Client: {c.name} -> {c.id}")

        # Admin bypasses membership checks entirely (see user_has_client_access) but we
        # still grant it for realism. The demo manager only gets access to the FIRST
        # client - deliberately, so User B (manager) NOT having access to Client B/C is
        # a real tenant-isolation scenario ready to test, not something to fabricate.
        for c in clients:
            _ensure_membership(db, admin, c)
        _ensure_membership(db, manager, clients[0])
        db.commit()
        print(f"Demo manager has membership on: {clients[0].name} only (by design, for tenant-isolation testing).")

        print("\nSeed complete (users/clients/memberships only - see the module docstring for why).")
        print(f"Demo admin clerk_id:   {DEMO_ADMIN_CLERK_ID}  (X-Demo-User header value, AUTH_MODE=demo)")
        print(f"Demo manager clerk_id: {DEMO_MANAGER_CLERK_ID}")
        print(f"Primary client id:     {clients[0].id}  ({clients[0].name})")
        print("\nNext: start the API server, then run:")
        print("    python -m scripts.demo_http_walkthrough")
        print("to upload sample documents and generate a real report/content through the live server.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
