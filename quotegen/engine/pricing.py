"""
Quote pricing engine.

Ported from the Excel workbook's formula chain:
    SalMat (salary + premium build-up)
      -> per-role staff cost (social security, wage inflation, attrition, hiring, equipment)
      -> + overhead (mode-dependent: TDCX incl/excl IT, Client Site, Remote, Hybrid)
      -> + margin (grossed up) + penalty provision (grossed up)
      -> agent-only monthly rate
      -> + fully-loaded support add-on (from span/ratio tab)
      -> final monthly rate per FTE
      -> FX convert to quote currency, apply VAT if selected, derive hourly rate from hours basis

All monetary figures are computed in the *site's local currency* first (matching
the Excel model), then converted to quote currency at the end.
"""
from dataclasses import dataclass, field
from typing import Optional


OVERHEAD_MODES = ["TDCX_INCL_IT", "TDCX_EXCL_IT", "REMOTE", "CLIENT_SITE", "HYBRID"]


@dataclass
class SalaryInputs:
    """Raw salary build-up for a role, in site local currency (from salary_matrix)."""
    base_salary: float
    salary_adjustment: float = 0.0
    language_native_premium: float = 0.0
    complexity_premium: float = 0.0
    tenure_premium: float = 0.0
    other_premium: float = 0.0
    bonus_annual: float = 0.0
    incentive: float = 0.0
    cash_benefit_1: float = 0.0        # "EXTRA" bucket (MX1 col N) -- confirm exact source with Finance
    cash_benefit_2: float = 0.0
    amortised_severance: float = 0.0   # MX1 col Y -- confirm source with Finance
    shift_allowance: float = 0.0

    @property
    def total_salary(self) -> float:
        return (
            self.base_salary
            + self.salary_adjustment
            + self.language_native_premium
            + self.complexity_premium
            + self.tenure_premium
            + self.other_premium
        )

    @property
    def total_comp_for_ss(self) -> float:
        """Base for social security calc: salary + bonus + incentive (excl. severance/allowances)."""
        return self.total_salary + self.bonus_annual + self.incentive

    @property
    def total_employee_compensation(self) -> float:
        """MX1 'TOTAL EMPLOYEE COMPENSATION' (AA col): salary+bonus+incentive+extra+severance+shift."""
        return (
            self.total_salary
            + self.bonus_annual
            + self.incentive
            + self.cash_benefit_1
            + self.shift_allowance
            + self.amortised_severance
        )

    # Backward-compat alias used elsewhere in the codebase
    @property
    def total_comp(self) -> float:
        return self.total_employee_compensation


@dataclass
class CountryDrivers:
    """Per-country cost drivers (from drivers.json)."""
    social_security_pct: float
    monthly_attrition: float
    annual_wage_inflation: float
    night_premium: float = 0.0
    night_allowance_lc: float = 0.0
    hiring_cost_flat_lc: float = 0.0    # MX1 'TOTAL HIRING' -- flat amount per role, confirm source with Finance
    equipment_cost_lc: float = 0.0      # MX1 'TOTAL EQUIPMENT'
    paid_hrs: float = 0
    logged_hrs: float = 0
    productive_hrs: float = 0


@dataclass
class OverheadRates:
    """Per-FTE overhead cost for a given mode, local currency (from overheads.json)."""
    shared_services: float
    it_telecom: float
    facilities: float
    general_overheads: float

    @property
    def total(self) -> float:
        return self.shared_services + self.it_telecom + self.facilities + self.general_overheads


@dataclass
class QuoteAssumptions:
    margin_pct: float               # J5 in Excel, e.g. 0.10
    penalty_pct: float = 0.0        # J3
    is_night_shift: bool = False
    fully_loaded: bool = True       # P5
    support_addon_local: float = 0.0  # from SpanLOB tab, local currency
    vat_pct: float = 0.0            # only applied if "include VAT" selected
    include_vat: bool = False
    fx_rate: float = 1.0            # quote_currency per local_currency (C6 in Excel)
    hours_basis: str = "productive"  # paid | logged | productive | other
    other_hours: Optional[float] = None


@dataclass
class RoleQuoteResult:
    total_salary: float
    total_comp: float
    staff_cost: float
    overhead: float
    total_cost: float
    margin_amount: float
    penalty_amount: float
    agent_only_rate: float          # local currency, before support add-on
    fully_loaded_rate: float        # local currency, agent_only + support add-on
    final_monthly_rate: float       # quote currency
    hourly_rate: float              # quote currency
    final_monthly_rate_with_vat: float
    hourly_rate_with_vat: float


def compute_staff_cost(salary: SalaryInputs, drivers: CountryDrivers) -> float:
    """
    Ported exactly from MX1 columns U-AH (validated against ground truth to the cent):

        total_employee_comp = salary+bonus+incentive+extra+shift+severance   (MX1 AA)
        social_security     = (salary+bonus+incentive) * ss_pct              (MX1 AB)
        hiring               = flat per-role hiring cost                      (MX1 AE)
        attrition            = (total_employee_comp + social_security + hiring) * attrition_pct  (MX1 AG)
        total_direct_costs  = total_employee_comp + social_security + hiring + equipment + attrition (MX1 AH)

    Note: wage inflation is applied as a *pricing-year* escalator elsewhere in the
    Excel (QGLOB1!J1 feeds SalMat, not this per-role block), not compounded here.
    """
    total_comp = salary.total_employee_compensation
    social_security = salary.total_comp_for_ss * drivers.social_security_pct
    hiring = drivers.hiring_cost_flat_lc
    equipment = drivers.equipment_cost_lc
    attrition = (total_comp + social_security + hiring) * drivers.monthly_attrition

    return total_comp + social_security + hiring + equipment + attrition


def compute_overhead(overhead: OverheadRates) -> float:
    return overhead.total


def gross_up(amount_before_markup: float, pct: float) -> float:
    """
    Excel pattern: BJ = BG/(1-N)*N  -> converts a target margin % of *revenue*
    into an additive amount on top of cost. Equivalent to: cost * pct / (1 - pct)
    """
    if pct >= 1:
        raise ValueError("Margin/penalty pct must be < 100%")
    return amount_before_markup * pct / (1 - pct)


def price_role(
    salary: SalaryInputs,
    drivers: CountryDrivers,
    overhead: OverheadRates,
    assumptions: QuoteAssumptions,
) -> RoleQuoteResult:
    staff_cost = compute_staff_cost(salary, drivers)
    oh = compute_overhead(overhead)
    total_cost = staff_cost + oh

    # Margin is grossed up on total cost; penalty is grossed up on (cost + margin) --
    # validated to the cent against ground truth.
    margin_amount = gross_up(total_cost, assumptions.margin_pct)
    cost_plus_margin = total_cost + margin_amount
    penalty_amount = gross_up(cost_plus_margin, assumptions.penalty_pct) if assumptions.penalty_pct else 0.0

    agent_only_rate_local = cost_plus_margin + penalty_amount

    fully_loaded_local = (
        agent_only_rate_local + assumptions.support_addon_local
        if assumptions.fully_loaded
        else agent_only_rate_local
    )

    final_monthly_rate = round(fully_loaded_local * assumptions.fx_rate, 2)

    hours_map = {
        "paid": drivers.paid_hrs,
        "logged": drivers.logged_hrs,
        "productive": drivers.productive_hrs,
        "other": assumptions.other_hours,
    }
    hours = hours_map.get(assumptions.hours_basis)
    hourly_rate = round(final_monthly_rate / hours, 2) if hours else 0.0

    vat_multiplier = (1 + assumptions.vat_pct) if assumptions.include_vat else 1.0
    final_with_vat = round(final_monthly_rate * vat_multiplier, 2)
    hourly_with_vat = round(hourly_rate * vat_multiplier, 2)

    return RoleQuoteResult(
        total_salary=salary.total_salary,
        total_comp=salary.total_comp,
        staff_cost=staff_cost,
        overhead=oh,
        total_cost=total_cost,
        margin_amount=margin_amount,
        penalty_amount=penalty_amount,
        agent_only_rate=agent_only_rate_local,
        fully_loaded_rate=fully_loaded_local,
        final_monthly_rate=final_monthly_rate,
        hourly_rate=hourly_rate,
        final_monthly_rate_with_vat=final_with_vat,
        hourly_rate_with_vat=hourly_with_vat,
    )


@dataclass
class QuoteLineItem:
    role: str
    shift: str
    fte_ordered: float
    contingency_fte: float = 0.0
    result: Optional[RoleQuoteResult] = None

    @property
    def fte_hired(self) -> float:
        return self.fte_ordered + self.contingency_fte

    @property
    def monthly_total(self) -> float:
        if not self.result:
            return 0.0
        return round(self.result.final_monthly_rate * self.fte_ordered, 2)
