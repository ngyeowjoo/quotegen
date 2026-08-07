"""
Seed Supabase with master data extracted from the Excel workbook.

Run this AFTER applying supabase/schema.sql in the Supabase SQL Editor.

Usage:
    pip install supabase python-dotenv
    export SUPABASE_URL="https://kqyubyfyqtwuakzykmtg.supabase.co"
    export SUPABASE_SERVICE_KEY="<service_role key -- NOT the public/anon key>"
    python3 seed_supabase.py

NOTE: seeding writes master data, which is blocked by the RLS policies for
normal users -- you must use the *service_role* key (Project Settings > API)
for this one-time seed, not the publishable/anon key used by the app itself.
Never put the service_role key in the Streamlit app or commit it to git.
"""
import os
import json
import sys
from pathlib import Path

from supabase import create_client

DATA_DIR = Path(__file__).parent / "data"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    sys.exit(
        "Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables first "
        "(service_role key from Project Settings > API -- not the public key)."
    )

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def load(filename):
    with open(DATA_DIR / filename) as f:
        return json.load(f)


def seed_table(table_name, rows, on_conflict=None):
    if not rows:
        print(f"  skip {table_name} (no rows)")
        return
    # Upsert in batches of 200 to stay well under request size limits
    batch_size = 200
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        q = sb.table(table_name).upsert(batch, on_conflict=on_conflict) if on_conflict else sb.table(table_name).insert(batch)
        q.execute()
    print(f"  seeded {table_name}: {len(rows)} rows")


def main():
    print("Seeding countries_drivers...")
    seed_table("countries_drivers", load("drivers.json"), on_conflict="city")

    print("Seeding base_salary_db...")
    seed_table("base_salary_db", load("base_salary_db.json"), on_conflict="campaign_type,role,native_flag,city")

    print("Seeding overheads...")
    seed_table("overheads", load("overheads.json"), on_conflict="overhead_mode")

    print("Seeding fx_rates...")
    seed_table("fx_rates", load("fx_rates.json"), on_conflict="currency")

    print("Seeding tax_rates...")
    seed_table("tax_rates", load("tax_rates.json"), on_conflict="country,biz_unit")

    print("Seeding campaign_types...")
    campaign_rows = [
        {"display_name": c["type"], "key": c["key"], "description": c.get("description")}
        for c in load("campaign_types.json")
    ]
    seed_table("campaign_types", campaign_rows, on_conflict="key")

    print("Seeding span_ratios...")
    span = load("span_ratios_lob1.json")
    seed_table("span_ratios", [{**span, "lob": "LOB1"}], on_conflict="lob")

    print("\nDone. Verify row counts in the Supabase Table Editor.")


if __name__ == "__main__":
    main()
