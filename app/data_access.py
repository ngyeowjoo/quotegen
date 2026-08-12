"""
Data access layer -- reads master data from data/master_data.xlsx (checked into
git). Finance/HR update master data by editing that file directly and pushing
to the repo -- no database required. Good for a prototype/demo; swap this
module for Supabase (or another DB) later without touching the rest of the app.
"""
from pathlib import Path
from functools import lru_cache
import pandas as pd
import streamlit as st

DATA_FILE = Path(__file__).parent.parent / "data" / "master_data.xlsx"


@st.cache_data
def _load_sheet(sheet_name):
    df = pd.read_excel(DATA_FILE, sheet_name=sheet_name)
    return df.to_dict(orient="records")


def get_drivers():
    return _load_sheet("Drivers")


def get_base_salary_db():
    return _load_sheet("BaseSalary")


def get_overheads():
    return _load_sheet("Overheads")


def get_fx_rates():
    return _load_sheet("FXRates")


def get_tax_rates():
    return _load_sheet("TaxRates")


def get_campaign_types():
    rows = _load_sheet("CampaignTypes")
    return [{"type": r["type"], "key": r["key"], "description": r.get("description")} for r in rows]


def get_span_ratios():
    rows = _load_sheet("SpanRatios")
    return rows[0] if rows else {}


def get_support_ratios():
    return _load_sheet("SupportRatios")


def list_cities():
    return sorted({d["city"] for d in get_drivers() if d.get("city")})


def get_driver_for_city(city):
    for d in get_drivers():
        if d["city"] == city:
            return d
    return None


def get_country_for_city(city):
    d = get_driver_for_city(city)
    return d["country"] if d else None


def get_tax_for_city(city):
    country = get_country_for_city(city)
    for t in get_tax_rates():
        if t["country"] == country:
            return t
    return None


def list_roles_for_campaign(campaign_type):
    roles = {r["role"] for r in get_base_salary_db() if r["campaign_type"] == campaign_type}
    return sorted(roles)


def get_base_salary(campaign_type, role, city):
    for r in get_base_salary_db():
        if r["campaign_type"] == campaign_type and r["role"] == role and r["city"] == city:
            return r["base_salary"]
    return None


def get_support_base_salary(role, city):
    """Support-role salaries live under campaign_type 'SUPPORT' in BaseSalary."""
    for r in get_base_salary_db():
        if r["campaign_type"] == "SUPPORT" and r["role"] == role and r["city"] == city:
            return r["base_salary"]
    return None


def get_overhead_rates(mode):
    for o in get_overheads():
        if o["overhead_mode"] == mode:
            return o
    return None


def get_fx_rate_per_usd(currency):
    for f in get_fx_rates():
        if f["currency"] == currency:
            return f["rate_per_usd"]
    return 1.0


def clear_cache():
    """Call after editing data/master_data.xlsx (e.g. via the Master Data Editor page)."""
    _load_sheet.clear()
