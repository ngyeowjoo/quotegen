"""
Data access layer -- reads master data from Supabase (RLS-protected).
Falls back to local data/*.json only if used outside Streamlit (e.g. quick
scripts) via the `_local_fallback` helpers -- the live app always uses Supabase.
"""
from functools import lru_cache
from app.supabase_client import get_client


def _table(name):
    return get_client().table(name)


@lru_cache
def get_drivers():
    return _table("countries_drivers").select("*").execute().data


@lru_cache
def get_base_salary_db():
    # Paginate: Supabase default caps at 1000 rows per request
    rows, offset, page = [], 0, 1000
    while True:
        chunk = _table("base_salary_db").select("*").range(offset, offset + page - 1).execute().data
        rows.extend(chunk)
        if len(chunk) < page:
            break
        offset += page
    return rows


@lru_cache
def get_overheads():
    return _table("overheads").select("*").execute().data


@lru_cache
def get_fx_rates():
    return _table("fx_rates").select("*").execute().data


@lru_cache
def get_tax_rates():
    return _table("tax_rates").select("*").execute().data


@lru_cache
def get_campaign_types():
    rows = _table("campaign_types").select("*").execute().data
    # normalize to the same shape the UI expects: {"type": ..., "key": ..., "description": ...}
    return [{"type": r["display_name"], "key": r["key"], "description": r.get("description")} for r in rows]


@lru_cache
def get_span_ratios(lob="LOB1"):
    rows = _table("span_ratios").select("*").eq("lob", lob).execute().data
    return rows[0] if rows else {}


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
    """Call after an admin edits master data so the app picks up fresh values."""
    get_drivers.cache_clear()
    get_base_salary_db.cache_clear()
    get_overheads.cache_clear()
    get_fx_rates.cache_clear()
    get_tax_rates.cache_clear()
    get_campaign_types.cache_clear()
    get_span_ratios.cache_clear()
