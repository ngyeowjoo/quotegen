"""
Validation test: reproduce the exact Excel output for the known example, to the cent.

Source (QGLOB1, Cloudwise / Singapore quote; MX1 row 112 + SpanLOB1!J6):
    Campaign: CUSTOMER_SERVICE, Role: JuniorAgentType4, Shift: Day
    Overheads mode: CLIENT SITE, Fully loaded: Yes
    Margin: 10%, Penalty provision: 15%, Monthly attrition: 2%
    Quote currency = local currency (SGD), no VAT
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.pricing import (
    SalaryInputs, CountryDrivers, OverheadRates, QuoteAssumptions, price_role
)


def test_singapore_customer_service_junior_agent4_day_client_site():
    salary = SalaryInputs(
        base_salary=3500,
        salary_adjustment=500,
        bonus_annual=333,
        incentive=445,
        cash_benefit_1=86.66,
        amortised_severance=166.6667,
    )
    assert salary.total_salary == 4000
    assert round(salary.total_employee_compensation, 2) == 5031.33

    drivers = CountryDrivers(
        social_security_pct=0.17,
        monthly_attrition=0.02,
        annual_wage_inflation=0.02,
        hiring_cost_flat_lc=200,
        equipment_cost_lc=0,
        paid_hrs=195,
        logged_hrs=157,
        productive_hrs=125,
    )

    overhead = OverheadRates(
        shared_services=1017,
        it_telecom=0,
        facilities=0,
        general_overheads=107,
    )
    assert overhead.total == 1124

    assumptions = QuoteAssumptions(
        margin_pct=0.10,
        penalty_pct=0.15,
        fully_loaded=True,
        support_addon_local=1870.00,
        include_vat=False,
        fx_rate=1.0,
        hours_basis="other",
        other_hours=140,
    )

    result = price_role(salary, drivers, overhead, assumptions)

    assert round(result.staff_cost, 2) == 6164.46
    assert round(result.total_cost, 2) == 7288.46
    assert round(result.agent_only_rate, 2) == 9527.40
    assert round(result.fully_loaded_rate, 2) == 11397.40
    assert result.final_monthly_rate == 11397.40
    assert result.hourly_rate == round(11397.40 / 140, 2)

    print("PASS -- all figures match Excel ground truth to the cent:")
    print(f"  staff_cost         = {result.staff_cost:.2f}")
    print(f"  total_cost         = {result.total_cost:.2f}")
    print(f"  agent_only_rate    = {result.agent_only_rate:.2f}")
    print(f"  fully_loaded_rate  = {result.fully_loaded_rate:.2f}")
    print(f"  final_monthly_rate = {result.final_monthly_rate:.2f}")
    print(f"  hourly_rate        = {result.hourly_rate:.2f}")


if __name__ == "__main__":
    test_singapore_customer_service_junior_agent4_day_client_site()
