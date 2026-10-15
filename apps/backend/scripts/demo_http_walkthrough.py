"""
Live HTTP walkthrough against a running DeepInsight OS dev/demo server.

Run scripts/seed_demo.py first, then start the API server (AUTH_MODE=demo,
VECTOR_STORE_PROVIDER=memory, CELERY_EAGER=true - see docs/DEV_DEMO_MODE.md), then run
this script. Every call here goes over real HTTP to the real running app - not direct
service calls - so this exercises the exact same path the frontend uses, and populates
the server's own in-memory vector store correctly (see scripts/seed_demo.py's docstring
for why that has to happen in-process).

Also doubles as a live tenant-isolation attack test: the demo manager user only has
membership on the first seeded client, so this script deliberately tries (and expects
to fail) reading/uploading-to a client it doesn't own.
"""
import sys
import time

import httpx

BASE_URL = "http://localhost:8000/api/v1"
ADMIN_HEADERS = {"Authorization": "Bearer demo", "X-Demo-User": "demo-admin"}
MANAGER_HEADERS = {"Authorization": "Bearer demo", "X-Demo-User": "demo-manager"}

SAMPLE_DOCUMENTS = [
    (
        "brand_voice.md",
        "text/markdown",
        """# Aurora Wellness Collective - Brand Voice Guide

Our brand voice is warm, grounded, and encouraging - never clinical, never pushy.
We speak like a trusted friend who happens to know a lot about wellness, not like a
sales brochure.

## Tone principles
- Calm confidence, not hype.
- Plain language over jargon - we avoid words like "biohack" or "optimize."
- Always inclusive of different bodies, budgets, and fitness levels.

## Target audience
Busy professionals aged 28-45 in mid-size cities who want sustainable wellness habits,
not extreme transformations. They are skeptical of fad diets and value authenticity
over influencer hype.

## Positioning
Aurora is the wellness studio that meets you where you are. We are not a bootcamp.
We are a long-term partner in feeling better, one small habit at a time.
""",
    ),
    (
        "q3_campaign_notes.md",
        "text/markdown",
        """# Aurora Wellness Collective - Active Campaigns (Q3)

## "Small Habits, Real Change" campaign
Running across email and organic social through the end of Q3. Goal: drive new
studio-visit bookings from our nurture list without discounting aggressively.

## Objectives
- Increase newsletter-to-booking conversion rate.
- Reduce landing page bounce rate on the "First Class Free" page.
- Build a library of client success stories for future content.

## Key messaging
Every campaign should reinforce that Aurora is a long-term habit partner, not a quick
fix. Avoid before/after transformation photos - focus on how clients *feel*.
""",
    ),
]


def _fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def main():
    with httpx.Client(base_url=BASE_URL, timeout=120.0) as client:
        print("=== Finding seeded clients (as demo-admin) ===")
        resp = client.get("/clients/", headers=ADMIN_HEADERS)
        resp.raise_for_status()
        clients = resp.json()
        by_name = {c["name"]: c for c in clients}
        if "Aurora Wellness Collective" not in by_name:
            _fail("Aurora Wellness Collective not found - did you run `python -m scripts.seed_demo` first?")
        primary = by_name["Aurora Wellness Collective"]
        other = by_name.get("Northstar Legal Partners")
        print(f"  primary client: {primary['id']} ({primary['name']})")

        print("\n=== Uploading sample documents (as demo-admin) ===")
        doc_ids = []
        for filename, content_type, text in SAMPLE_DOCUMENTS:
            files = {"file": (filename, text.encode("utf-8"), content_type)}
            data = {"client_id": primary["id"]}
            resp = client.post("/documents/upload", headers=ADMIN_HEADERS, data=data, files=files)
            if resp.status_code != 200:
                _fail(f"upload {filename} -> {resp.status_code} {resp.text}")
            body = resp.json()
            doc_ids.append(body["document_id"])
            print(f"  uploaded {filename} -> {body['document_id']} (status={body['status']})")

        print("\n=== Querying the knowledge base (as demo-admin) ===")
        resp = client.post("/knowledge/query", headers=ADMIN_HEADERS,
                            params={"client_id": primary["id"], "query": "What is the brand voice?"})
        resp.raise_for_status()
        result = resp.json()
        print(f"  grounded={result['grounded']} sources={len(result.get('sources', []))}")
        if not result["grounded"]:
            _fail("expected grounded=True after uploading real documents")

        print("\n=== TENANT ISOLATION ATTACK: demo-manager reading a client it doesn't own ===")
        if other:
            resp = client.get(f"/clients/{other['id']}", headers=MANAGER_HEADERS)
            print(f"  GET /clients/{other['id']} as demo-manager -> {resp.status_code}")
            if resp.status_code not in (403, 404):
                _fail(f"expected 403/404 for cross-tenant client read, got {resp.status_code}: {resp.text}")
            print("  correctly denied.")

        print("\n=== TENANT ISOLATION ATTACK: demo-manager uploading to a client it doesn't own ===")
        if other:
            files = {"file": ("attack.txt", b"cross-tenant upload attempt", "text/plain")}
            resp = client.post("/documents/upload", headers=MANAGER_HEADERS,
                                data={"client_id": other["id"]}, files=files)
            print(f"  POST /documents/upload (client={other['id']}) as demo-manager -> {resp.status_code}")
            if resp.status_code not in (403, 404):
                _fail(f"expected 403/404 for cross-tenant upload, got {resp.status_code}: {resp.text}")
            print("  correctly denied.")

        print("\n=== TENANT ISOLATION: demo-manager CAN access its own client ===")
        resp = client.get(f"/clients/{primary['id']}", headers=MANAGER_HEADERS)
        if resp.status_code != 200:
            _fail(f"expected 200 for own-client read, got {resp.status_code}: {resp.text}")
        print(f"  GET /clients/{primary['id']} as demo-manager -> 200 (correct - has membership)")

        print("\n=== Generating a real report (as demo-admin) ===")
        t0 = time.monotonic()
        resp = client.post(
            "/reports/generate",
            headers=ADMIN_HEADERS,
            params={"client_id": primary["id"], "reporting_period": "2026-Q3"},
            json={"metrics": {"ctr": 0.041, "bounce_rate": 0.29, "sessions": 4210, "conversion_rate": 0.052},
                  "historical_metrics": {"ctr": 0.021, "bounce_rate": 0.38, "sessions": 3100, "conversion_rate": 0.041}},
        )
        resp.raise_for_status()
        body = resp.json()
        print(f"  status={body['status']} ({time.monotonic() - t0:.1f}s): {body.get('result') or body.get('error')}")

        print("\n=== Generating real content (as demo-admin) ===")
        t0 = time.monotonic()
        resp = client.post(
            "/content/generate",
            headers=ADMIN_HEADERS,
            params={"client_id": primary["id"], "content_type": "Blog",
                    "target_audience": "busy professionals aged 28-45",
                    "goal": "Promote the 'Small Habits, Real Change' campaign without discounting."},
        )
        resp.raise_for_status()
        body = resp.json()
        print(f"  status={body['status']} ({time.monotonic() - t0:.1f}s): {body.get('result') or body.get('error')}")

        print("\n=== Walkthrough complete. No unexpected failures. ===")


if __name__ == "__main__":
    main()
