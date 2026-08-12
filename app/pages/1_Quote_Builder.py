import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

from app.data_access import (
    list_cities, get_driver_for_city, get_tax_for_city, get_campaign_types,
    list_roles_for_campaign, get_base_salary, get_support_base_salary,
    get_overhead_rates, get_fx_rate_per_usd, get_support_ratios,
)
from engine.pricing import (
    SalaryInputs, CountryDrivers, OverheadRates, QuoteAssumptions, price_role,
    QuoteLineItem, OVERHEAD_MODES,
)

st.set_page_config(page_title="Quote Builder", page_icon="🧮", layout="wide")
st.title("🧮 Quote Builder")

if "line_items" not in st.session_state:
    st.session_state.line_items = []


def build_result(base_salary, city, overhead_mode, margin_pct, penalty_pct,
                  quote_currency, hours_basis, other_hours, include_vat, shift):
    driver = get_driver_for_city(city)
    tax = get_tax_for_city(city)
    oh_rates = get_overhead_rates(overhead_mode)

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
        fully_loaded=False,          # support is shown as its own line items now, not baked in
        support_addon_local=0.0,
        vat_pct=(tax["vat_pct"] if tax else 0) or 0,
        include_vat=include_vat,
        fx_rate=fx_rate,
        hours_basis=hours_basis,
        other_hours=other_hours,
    )

    result = price_role(salary, drivers, overhead, assumptions)
    return result, out_currency


# ---- Quote-level settings ----
with st.expander("Quote settings", expanded=True):
    c1, c2, c3 = st.columns(3)
    client_name = c1.text_input("Client name", "")
    project_name = c2.text_input("Project / SOW name", "")
    quote_currency = c3.selectbox("Quote currency", ["Local (site currency)", "SGD", "USD"], index=0)

    c4, c5, c6 = st.columns(3)
    margin_pct = c4.number_input(
        "Default net margin %", min_value=0.0, max_value=50.0, value=10.0,
        help="Pre-fills each new line item. You can still override margin per role below."
    ) / 100
    penalty_pct = c5.number_input("Default penalty provision %", min_value=0.0, max_value=50.0, value=15.0) / 100
    overhead_mode = c6.selectbox("Overheads mode", OVERHEAD_MODES, index=3)

    c7, c8, c9 = st.columns(3)
    include_support = c7.checkbox("Auto-add support staff (Ops Mgr, Team Lead, QA, Trainer, BA)", value=True)
    include_vat = c8.checkbox("Include VAT / sales tax?", value=False)
    hours_basis = c9.selectbox("Billable hours basis", ["paid", "logged", "productive", "other"], index=2)

    other_hours = None
    if hours_basis == "other":
        other_hours = st.number_input("Hours per month (Other)", min_value=1.0, value=140.0)

    st.caption(
        "All figures pulled from the database (salaries, overheads, drivers) are "
        "**reference defaults** — every field below can be overridden per line item "
        "before you add it to the quote."
    )

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

db_salary = get_base_salary(campaign_type, role, city)
oc1, oc2, oc3 = st.columns(3)
salary_override = oc1.number_input(
    "Base salary (editable, local currency)",
    value=float(db_salary) if db_salary is not None else 0.0,
    help="Pre-filled from the database. Change it to quote a non-standard rate for this deal.",
)
role_margin = oc2.number_input("Margin % for this role", min_value=0.0, max_value=50.0,
                                value=margin_pct * 100) / 100
role_penalty = oc3.number_input("Penalty % for this role", min_value=0.0, max_value=50.0,
                                 value=penalty_pct * 100) / 100

if db_salary is None:
    st.warning(f"No database salary found for {campaign_type} / {role} / {city} — enter one manually above.")

if st.button("➕ Add role to quote", type="primary"):
    result, out_currency = build_result(
        salary_override, city, overhead_mode, role_margin, role_penalty,
        quote_currency, hours_basis, other_hours, include_vat, shift,
    )
    item = QuoteLineItem(
        role=f"{campaign_type_display} / {role} ({city}, {shift})",
        shift=shift, fte_ordered=fte, contingency_fte=0, result=result,
    )
    st.session_state.line_items.append({
        "item": item, "currency": out_currency, "kind": "agent", "city": city,
    })
    st.success(f"Added: {item.role} — {result.final_monthly_rate:,.2f} {out_currency}/FTE/month")

    if include_support:
        support_ratios = [r for r in get_support_ratios() if r["include_by_default"]]
        added_support = []
        for sr in support_ratios:
            ratio = sr["ratio_1_to_n_agents"]
            support_fte = round(fte / ratio) if ratio else 0
            if support_fte < 1:
                continue
            support_salary = get_support_base_salary(sr["role"], city)
            if support_salary is None:
                continue
            sresult, s_currency = build_result(
                support_salary, city, overhead_mode, role_margin, role_penalty,
                quote_currency, hours_basis, other_hours, include_vat, "Day",
            )
            sitem = QuoteLineItem(
                role=f"Support / {sr['role']} ({city}) — 1:{int(ratio)} ratio",
                shift="Day", fte_ordered=support_fte, contingency_fte=0, result=sresult,
            )
            st.session_state.line_items.append({
                "item": sitem, "currency": s_currency, "kind": "support", "city": city,
            })
            added_support.append(f"{sr['role']} x{support_fte}")
        if added_support:
            st.info(f"Auto-added support staff: {', '.join(added_support)}. "
                    "Adjust or remove any of these below.")

st.divider()

# ---- Quote summary ----
st.subheader("Quote summary")
if not st.session_state.line_items:
    st.caption("No roles added yet.")
else:
    grand_total = 0
    for idx, li in enumerate(st.session_state.line_items):
        item = li["item"]
        r = item.result
        monthly_total = round(r.final_monthly_rate * item.fte_ordered, 2)
        grand_total += monthly_total

        badge = "🧑‍💼 Agent" if li["kind"] == "agent" else "🛠️ Support"
        header = f"{badge} — {item.role} — {item.fte_ordered} FTE — {monthly_total:,.2f} {li['currency']}/mo"

        with st.expander(header):
            cA, cB, cC = st.columns(3)
            cA.metric("Rate / FTE / Month", f"{r.final_monthly_rate:,.2f} {li['currency']}")
            cB.metric("Hourly Rate", f"{r.hourly_rate:,.2f} {li['currency']}")
            cC.metric("Monthly Total", f"{monthly_total:,.2f} {li['currency']}")

            st.markdown("**How this rate was calculated:**")
            breakdown = pd.DataFrame([
                {"Step": "Total salary (base + adjustments + premiums)", "Amount": f"{r.total_salary:,.2f}"},
                {"Step": "Total employee compensation (+bonus/incentive/extras)", "Amount": f"{r.total_comp:,.2f}"},
                {"Step": "+ Social security / attrition / hiring / equipment", "Amount": f"{(r.staff_cost - r.total_comp):,.2f}"},
                {"Step": "= Total staff cost", "Amount": f"{r.staff_cost:,.2f}"},
                {"Step": "+ Overheads (selected mode)", "Amount": f"{r.overhead:,.2f}"},
                {"Step": "= Total cost", "Amount": f"{r.total_cost:,.2f}"},
                {"Step": "+ Margin (grossed up)", "Amount": f"{r.margin_amount:,.2f}"},
                {"Step": "+ Penalty provision (grossed up)", "Amount": f"{r.penalty_amount:,.2f}"},
                {"Step": "= Rate before FX/VAT (local currency)", "Amount": f"{r.agent_only_rate:,.2f}"},
                {"Step": "Final monthly rate (after FX)", "Amount": f"{r.final_monthly_rate:,.2f} {li['currency']}"},
                {"Step": "Hourly rate", "Amount": f"{r.hourly_rate:,.2f} {li['currency']}"},
            ])
            st.dataframe(breakdown, hide_index=True, use_container_width=True)

            if st.button("🗑️ Remove this line", key=f"remove_{idx}"):
                st.session_state.line_items.pop(idx)
                st.rerun()

    st.metric("Grand total (monthly)", f"{grand_total:,.2f} {st.session_state.line_items[0]['currency']}")

    c1, c2 = st.columns(2)
    if c1.button("🗑️ Clear entire quote"):
        st.session_state.line_items = []
        st.rerun()

    # ---- Build downloadable quote workbook ----
    quote_rows = []
    for li in st.session_state.line_items:
        item = li["item"]
        r = item.result
        quote_rows.append({
            "Type": "Agent" if li["kind"] == "agent" else "Support",
            "Role": item.role,
            "City": li["city"],
            "Shift": item.shift,
            "FTE": item.fte_ordered,
            "Rate per FTE per Month": r.final_monthly_rate,
            "Hourly Rate": r.hourly_rate,
            "Monthly Total": round(r.final_monthly_rate * item.fte_ordered, 2),
            "Currency": li["currency"],
        })
    quote_df = pd.DataFrame(quote_rows)

    header_df = pd.DataFrame([{
        "Client": client_name or "(not set)",
        "Project": project_name or "",
        "Overhead Mode": overhead_mode,
        "Default Margin %": f"{margin_pct*100:.1f}%",
        "Default Penalty %": f"{penalty_pct*100:.1f}%",
        "Hours Basis": hours_basis,
        "VAT Included": include_vat,
        "Grand Total (Monthly)": f"{grand_total:,.2f} {st.session_state.line_items[0]['currency']}",
    }])

    from io import BytesIO
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        header_df.to_excel(writer, sheet_name="Quote Summary", index=False)
        quote_df.to_excel(writer, sheet_name="Line Items", index=False)
    buffer.seek(0)

    c2.download_button(
        "⬇️ Download quote as Excel",
        data=buffer,
        file_name=f"quote_{(client_name or 'draft').replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

st.caption("Prototype: quotes aren't saved centrally yet — use the download button to keep a copy.")
