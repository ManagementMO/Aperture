"""Seed the user's Supabase project with 10k fake customer rows.

Uses Composio's SUPABASE_BETA_RUN_SQL_QUERY tool — same path the live
agent uses. Idempotent (DROPs existing table first).

Run:
    .venv/bin/python scripts/seed_supabase_customers.py
"""

from __future__ import annotations

import json
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from composio import Composio                       # noqa: E402
from composio_anthropic import AnthropicProvider    # noqa: E402

ROW_COUNT = 10_000


def _execute(client, slug: str, args: dict, user_id: str):
    raw = client.tools.execute(
        slug, args, user_id=user_id, dangerously_skip_version_check=True,
    )
    if isinstance(raw, dict):
        ok = bool(raw.get("successful", True))
        err = raw.get("error") if not ok else None
        data = raw.get("data", raw)
    else:
        ok = bool(getattr(raw, "successful", True))
        err = getattr(raw, "error", None) if not ok else None
        data = getattr(raw, "data", raw)
    if isinstance(data, dict) and set(data.keys()) == {"data"}:
        data = data["data"]
    return ok, err, data


# ---------------------------------------------------------------------------
# Resolve user_id (prefer COMPOSIO_USER_ID, else first ACTIVE supabase account)
# ---------------------------------------------------------------------------

def _resolve_user_id(client) -> str:
    import os
    explicit = os.getenv("COMPOSIO_USER_ID")
    if explicit:
        try:
            accs = client.connected_accounts.list(user_ids=[explicit])
            if accs.items:
                return explicit
        except Exception:
            pass
    accs = client.connected_accounts.list()
    for a in accs.items:
        if a.status == "ACTIVE" and a.toolkit.slug == "supabase":
            return a.user_id
    for a in accs.items:
        if a.status == "ACTIVE":
            return a.user_id
    raise RuntimeError("no active connected accounts")


def _find_project_ref(client, user_id: str) -> str:
    print("→ listing Supabase projects…")
    ok, err, data = _execute(
        client, "SUPABASE_LIST_ALL_PROJECTS", {}, user_id,
    )
    if not ok:
        raise RuntimeError(f"LIST_ALL_PROJECTS failed: {err}")
    if isinstance(data, list):
        projects = data
    elif isinstance(data, dict):
        projects = (
            data.get("details")
            or data.get("projects")
            or data.get("items")
            or []
        )
    else:
        projects = []
    if not projects:
        raise RuntimeError(
            "no Supabase projects on this account — create one in the "
            "Supabase dashboard before seeding."
        )
    p = projects[0]
    ref = p.get("id") or p.get("ref") or p.get("project_ref")
    name = p.get("name", "?")
    region = p.get("region", "?")
    print(f"   using project: {name} ({ref}) · region {region}")
    if len(projects) > 1:
        print(f"   ({len(projects) - 1} other project(s) skipped)")
    return ref


# ---------------------------------------------------------------------------
# Seed SQL — single round-trip insert via generate_series
# ---------------------------------------------------------------------------

_DDL = """
DROP TABLE IF EXISTS public.customers;
CREATE TABLE public.customers (
  id              BIGSERIAL PRIMARY KEY,
  name            TEXT NOT NULL,
  email           TEXT NOT NULL UNIQUE,
  company         TEXT,
  signup_date     DATE,
  plan            TEXT,
  monthly_spend   NUMERIC(10,2),
  country         TEXT,
  status          TEXT,
  last_active     TIMESTAMP
);
"""

_SEED = f"""
INSERT INTO public.customers (
  name, email, company, signup_date, plan,
  monthly_spend, country, status, last_active
)
SELECT
  (ARRAY[
    'Alex','Bailey','Chen','Devi','Esra','Farah','Gomez','Hayato',
    'Imani','Jules','Kira','Liam','Maya','Nikhil','Omar','Priya',
    'Quinn','Rohan','Saoirse','Tariq','Uma','Vega','Wren','Xiu','Yael','Zara'
  ])[(i % 26) + 1] || ' ' ||
  (ARRAY[
    'Cooper','Davis','Edwards','Foster','Gupta','Huang','Iyer','Jin',
    'Kim','Levy','Moore','Nair','Owens','Patel','Reyes','Singh',
    'Tran','Voss','Walsh','Xu','Young','Zhao'
  ])[(i % 22) + 1]                                                                  AS name,
  'user' || i || '@example.com'                                                     AS email,
  (ARRAY[
    'Acme Corp','Globex','Initech','Soylent','Hooli','Massive Dynamic',
    'Wonka Industries','Stark Industries','Wayne Enterprises','Cyberdyne'
  ])[(i % 10) + 1]                                                                  AS company,
  ('2024-01-01'::date + ((i * 13) % 540))                                           AS signup_date,
  (ARRAY['free','starter','pro','team','enterprise'])[(i % 5) + 1]                  AS plan,
  ROUND((random() * 999 + 1)::numeric, 2)                                           AS monthly_spend,
  (ARRAY['US','UK','CA','DE','FR','JP','AU','BR','IN','NL','MX','SG'])[(i % 12) + 1] AS country,
  (ARRAY['active','active','active','trial','churned','paused'])[(i % 6) + 1]      AS status,
  (NOW() - ((i % 120) || ' days')::interval)                                        AS last_active
FROM generate_series(1, {ROW_COUNT}) AS s(i);
"""


def main() -> int:
    client = Composio(provider=AnthropicProvider())
    user_id = _resolve_user_id(client)
    print(f"user_id   : {user_id}")
    project_ref = _find_project_ref(client, user_id)

    # 1) DDL
    print("→ creating fresh public.customers table…")
    t = time.perf_counter()
    ok, err, data = _execute(
        client, "SUPABASE_BETA_RUN_SQL_QUERY",
        {"project_ref": project_ref, "query": _DDL.strip()},
        user_id,
    )
    print(f"   DDL → ok={ok}  {(time.perf_counter()-t)*1000:.0f}ms")
    if not ok:
        print(f"   error: {err}\n   payload: {json.dumps(data, default=str)[:300]}")
        return 1

    # 2) Seed
    print(f"→ inserting {ROW_COUNT:,} fake customer rows…")
    t = time.perf_counter()
    ok, err, data = _execute(
        client, "SUPABASE_BETA_RUN_SQL_QUERY",
        {"project_ref": project_ref, "query": _SEED.strip()},
        user_id,
    )
    elapsed = (time.perf_counter() - t) * 1000
    print(f"   seed → ok={ok}  {elapsed:.0f}ms")
    if not ok:
        print(f"   error: {err}\n   payload: {json.dumps(data, default=str)[:400]}")
        return 1

    # 3) Verify
    print("→ verifying row count…")
    ok, err, data = _execute(
        client, "SUPABASE_BETA_RUN_SQL_QUERY",
        {"project_ref": project_ref,
         "query": "SELECT COUNT(*) AS n FROM public.customers;"},
        user_id,
    )
    print(f"   count → ok={ok}  result={json.dumps(data, default=str)[:200]}")

    # 4) Sample
    ok, err, data = _execute(
        client, "SUPABASE_BETA_RUN_SQL_QUERY",
        {"project_ref": project_ref,
         "query": "SELECT id, name, email, plan, country, monthly_spend "
                  "FROM public.customers ORDER BY id LIMIT 5;"},
        user_id,
    )
    print("→ sample rows (first 5):")
    print(f"   {json.dumps(data, default=str, indent=2)[:600]}")

    print()
    print("✓ done. The agent can now answer asks like:")
    print("    return me the first 1000 rows of our supabase")
    print("    how many customers are on the pro plan")
    print("    average monthly_spend by country")
    return 0


if __name__ == "__main__":
    sys.exit(main())
