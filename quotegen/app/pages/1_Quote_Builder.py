import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

from app.auth import require_login, current_user
from app.supabase_client import get_client
from app.data_access import (
    list_cities, get_driver_for_city, get_tax_for_city, get_campaign_types,
    list_roles_for_campaign, get_base_salary, get_overhead_rates,
    get_fx_rate_per_usd, get_span_ratios,
)
from engine.pricing import (
    SalaryInputs, CountryDrivers, OverheadRates, QuoteAssumptions, price_role,
    QuoteLineItem, OVERHEAD_MODES,
)

st.set_page_config(page_title="Quote Builder", page_icon="🧮", layout="wide")
require_login()
user = current_user()

st.title("🧮 Quote Builder")

if "line_items" not in st.session_state:
    st.session_state.line_items = []

# ---- Quote-level settings ----
with st.expander("Quote settings", expanded=True):
    c1, c2, c3 = st.columns(3)
    client_name = c1.text_input("Client name", "")
    project_name = c2.text_input("Project / SOW name", "")
    quote_currency = c3.selectbox("Quote currency", ["Local (site currency)", "SGD", "USD"], index=0)

    c4, c5, c6 = st.columns(3)
    margin_pct = c4.number_input("Overall net margin %", min_value=5.0, max_value=50.0, value=10.0) / 100
    penalty_pct = c5.number_input("Penalty provision %", min_value=0.0, max_value=50.0, value=15.0) / 100
    overhead_mode = c6.selectbox("Overheads mode", OVERHEAD_MODES, index=3)  # CLIENT_SITE default

    c7, c8, c9 = st.columns(3)
    fully_loaded = c7.selectbox("Fully loaded (include support ratio)?", ["Yes", "No"]) == "Yes"
    include_vat = c8.checkbox("Include VAT / sales tax?", value=False)
    hours_basis = c9.selectbox("Billable hours basis", ["paid", "logged", "productive", "other"], index=2)

    other_hours = None
    if hours_basis == "other":
        other_hours = st.number_input("Hours per month (Other)", min_value=1.0, value=140.0)

st.divider()

# ---- Add a role ----
st.subheader("Add a role")
cities = list_cities()
campaign_type_options = {c["type"]: c["key"] for c in get_campaign_types()}

c1, c2, c3, c4, c5 = st.columns(5)
city = c1.selectbox("City / Site", cities, index=cities.index("Singapore") if "Singapore" in cities else 0)
campaign_type_display = c2.selectbox("Campaign type", list(campaign_type_options.keys()))
campaign_type = campaign_type_options[campaign_type_display]
roles_available = list_roles_for_campaign(campaign_type)
role = c3.selectbox("Role", roles_available if roles_available else ["(no roles found)"])
shift = c4.selectbox("Shift", ["Day", "Night"])
fte = c5.number_input("FTE ordered", min_value=1, value=10)

contingency_fte = st.number_input("Contingency FTE (buffer, optional)", min_value=0, value=0)

if st.button("➕ Add role to quote", type="primary"):
    base_salary = get_base_salary(campaign_type, role, city)
    if base_salary is None:
        st.error(f"No base salary found for {campaign_type} / {role} / {city}. "
                 "This role x city combination may not exist in the salary database.")
    else:
        driver = get_driver_for_city(city)
        tax = get_tax_for_city(city)
        oh_rates = get_overhead_rates(overhead_mode)
        span = get_span_ratios()

        salary = SalaryInputs(
            base_salary=base_salary,
            shift_allowance=(driver.get("night_allowance_lc") or 0) if shift == "Night" else 0,
        )
        drivers = CountryDrivers(
            social_security_pct=(tax["social_security_pct"] if tax else driver["social_security_pct"]) or 0,
            monthly_attrition=driver["monthly_attrition"] or 0,
            annual_wage_inflation=driver["annual_wage_inflation"] or 0,
            night_premium=driver.get("night_premium") or 0,
            paid_hrs=driver["paid_hrs"] or 0,
            logged_hrs=driver["logged_hrs"] or 0,
            productive_hrs=driver["productive_hrs"] or 0,
        )
        overhead = OverheadRates(
            shared_services=oh_rates["shared_services"] or 0,
            it_telecom=oh_rates["it_telecom"] or 0,
            facilities=oh_rates["facilities"] or 0,
            general_overheads=oh_rates["general_overheads"] or 0,
        )

        local_currency = tax["currency"] if tax else "USD"
        if quote_currency == "Local (site currency)":
            fx_rate = 1.0
            out_currency = local_currency
        else:
            local_per_usd = get_fx_rate_per_usd(local_currency)
            quote_per_usd = get_fx_rate_per_usd(quote_currency)
            fx_rate = quote_per_usd / local_per_usd if local_per_usd else 1.0
            out_currency = quote_currency

        assumptions = QuoteAssumptions(
            margin_pct=margin_pct,
            penalty_pct=penalty_pct,
            fully_loaded=fully_loaded,
            support_addon_local=span.get("fully_loaded_addon", 0) or 0,
            vat_pct=(tax["vat_pct"] if tax else 0) or 0,
            include_vat=include_vat,
            fx_rate=fx_rate,
            hours_basis=hours_basis,
            other_hours=other_hours,
        )

        result = price_role(salary, drivers, overhead, assumptions)
        item = QuoteLineItem(role=f"{campaign_type_display} / {role} ({city}, {shift})", shift=shift,
                              fte_ordered=fte, contingency_fte=contingency_fte, result=result)
        st.session_state.line_items.append({"item": item, "currency": out_currency})
        st.success(f"Added: {item.role} — {result.final_monthly_rate:,.2f} {out_currency}/FTE/month")

st.divider()

# ---- Quote summary ----
st.subheader("Quote summary")
if not st.session_state.line_items:
    st.caption("No roles added yet.")
else:
    rows = []
    grand_total = 0
    for li in st.session_state.line_items:
        item = li["item"]
        r = item.result
        monthly_total = round(r.final_monthly_rate * item.fte_ordered, 2)
        grand_total += monthly_total
        rows.append({
            "Role": item.role,
            "FTE": item.fte_ordered,
            "Rate/FTE/Month": f"{r.final_monthly_rate:,.2f}",
            "Hourly Rate": f"{r.hourly_rate:,.2f}",
            "Monthly Total": f"{monthly_total:,.2f}",
            "Currency": li["currency"],
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.metric("Grand total (monthly)", f"{grand_total:,.2f} {rows[0]['Currency']}")

    c1, c2 = st.columns(2)
    if c1.button("🗑️ Clear quote"):
        st.session_state.line_items = []
        st.rerun()

    if c2.button("💾 Save quote", type="primary"):
        if not client_name:
            st.error("Enter a client name before saving.")
        else:
            sb = get_client()
            quote_row = {
                "client_name": client_name,
                "project_name": project_name,
                "quote_currency": rows[0]["Currency"],
                "margin_pct": margin_pct,
                "penalty_pct": penalty_pct,
                "overhead_mode": overhead_mode,
                "fully_loaded": fully_loaded,
                "include_vat": include_vat,
                "hours_basis": hours_basis,
                "created_by": user.id,
            }
            quote_res = sb.table("quotes").insert(quote_row).execute()
            quote_id = quote_res.data[0]["id"]

            line_rows = []
            for li in st.session_state.line_items:
                item = li["item"]
                r = item.result
                line_rows.append({
                    "quote_id": quote_id,
                    "city": item.role.split("(")[-1].split(",")[0].strip(),
                    "campaign_type": item.role.split(" / ")[0],
                    "role": item.role,
                    "shift": item.shift,
                    "fte_ordered": item.fte_ordered,
                    "contingency_fte": item.contingency_fte,
                    "final_monthly_rate": r.final_monthly_rate,
                    "hourly_rate": r.hourly_rate,
                    "monthly_total": round(r.final_monthly_rate * item.fte_ordered, 2),
                    "calc_breakdown": r.__dict__,
                })
            sb.table("quote_line_items").insert(line_rows).execute()
            st.success(f"Quote saved (id: {quote_id[:8]}...).")

st.caption("Quotes are saved to your Supabase project once you click **Save quote**.")
