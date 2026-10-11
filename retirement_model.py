"""Deterministic retirement model, independent of Streamlit and pandas.

An age is a whole-year boundary. Contributions arrive at each pre-retirement
year end. Retirement withdrawals occur at the start of each month, proportionally
from all account balances, followed by growth at equivalent monthly rates.
"""

from dataclasses import dataclass
from math import isfinite


ACCOUNTS = ("401 k", "IRA", "Brokerage", "HYSA")
CATEGORIES = ("Housing", "Food", "Health", "Travel")
SCENARIOS = {
    "Average market": 0.10,
    "Below-average market": 0.08,
    "Significantly below-average market": 0.06,
}
HYSA_RATE = 0.03
STATES = (
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
    "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
    "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
    "Washington", "West Virginia", "Wisconsin", "Wyoming",
)


@dataclass(frozen=True)
class Plan:
    name: str
    current_age: int
    retirement_age: int
    plan_age: int
    state: str
    balances: dict[str, float]
    contributions: dict[str, float]
    expenses: dict[str, float]

    @property
    def monthly_expenses(self) -> float:
        return sum(self.expenses.values())


def validate_plan(plan: Plan) -> list[str]:
    errors = []
    if not plan.name.strip():
        errors.append("Enter your name.")
    ages = (plan.current_age, plan.retirement_age, plan.plan_age)
    if any(not isinstance(age, int) or isinstance(age, bool) or not 18 <= age <= 120 for age in ages):
        errors.append("Enter whole-number ages between 18 and 120.")
    elif not plan.current_age <= plan.retirement_age < plan.plan_age:
        errors.append("Current age must be at or before retirement age; Plan-to-Age must be after retirement age.")
    if plan.state not in STATES:
        errors.append("Select a retirement state.")
    for label, values, expected in (
        ("Balances", plan.balances, ACCOUNTS),
        ("Contributions", plan.contributions, ACCOUNTS),
        ("Expenses", plan.expenses, CATEGORIES),
    ):
        if set(values) != set(expected):
            errors.append(f"{label} must include every listed category.")
        if any(not isinstance(value, (int, float)) or not isfinite(value) or value < 0 for value in values.values()):
            errors.append(f"{label} must be finite, non-negative numbers.")
    return errors


def monthly_rates(market_rate: float) -> dict[str, float]:
    return {
        account: (1 + (HYSA_RATE if account == "HYSA" else market_rate)) ** (1 / 12) - 1
        for account in ACCOUNTS
    }


def retirement_month(balances: dict[str, float], rates: dict[str, float], expense: float):
    """Return new balances, paid withdrawal, growth, and unfunded expense."""
    total = sum(balances.values())
    paid = min(expense, total)
    fraction = paid / total if total > 0 else 0
    remaining = {account: value * (1 - fraction) for account, value in balances.items()}
    growth = {account: value * rates[account] for account, value in remaining.items()}
    closing = {account: remaining[account] + growth[account] for account in ACCOUNTS}
    return closing, paid, sum(growth.values()), max(0.0, expense - paid)


def project_scenario(plan: Plan, scenario: str, start_year: int) -> dict:
    errors = validate_plan(plan)
    if errors:
        raise ValueError(" ".join(errors))
    rate = SCENARIOS[scenario]
    rates = monthly_rates(rate)
    balances = dict(plan.balances)
    annual = [{"Year": start_year, "Age": plan.current_age, "Scenario": scenario,
               "Assets": sum(balances.values()), **balances}]
    monthly = []
    retirement_balances = dict(balances) if plan.current_age == plan.retirement_age else None
    first_shortfall = None
    cumulative_shortfall = 0.0
    month_count = (plan.plan_age - plan.current_age) * 12
    for month in range(month_count):
        age = plan.current_age + month / 12
        retired = month >= (plan.retirement_age - plan.current_age) * 12
        opening = sum(balances.values())
        contribution = paid = shortfall = 0.0
        if retired:
            balances, paid, growth, shortfall = retirement_month(balances, rates, plan.monthly_expenses)
            cumulative_shortfall += shortfall
            if shortfall > 0.005 and first_shortfall is None:
                first_shortfall = {"Age": age, "Year": start_year + month // 12,
                                   "Month": month % 12 + 1}
        else:
            growth = sum(balances[account] * rates[account] for account in ACCOUNTS)
            balances = {account: balances[account] * (1 + rates[account]) for account in ACCOUNTS}
            if (month + 1) % 12 == 0:
                contribution = sum(plan.contributions.values())
                balances = {account: balances[account] + plan.contributions[account] for account in ACCOUNTS}
        monthly.append({
            "Projection month": month + 1, "Year": start_year + month // 12,
            "Month": month % 12 + 1, "Age": age, "Scenario": scenario,
            "Phase": "Retirement" if retired else "Saving", "Opening assets": opening,
            "Growth": growth, "Contributions": contribution, "Expenses paid": paid,
            "Unfunded expenses": shortfall, "Closing assets": sum(balances.values()),
            **balances,
        })
        if (month + 1) % 12 == 0:
            end_age = plan.current_age + (month + 1) // 12
            annual.append({"Year": start_year + (month + 1) // 12,
                           "Age": end_age, "Scenario": scenario,
                           "Assets": sum(balances.values()), **balances})
            if end_age == plan.retirement_age:
                retirement_balances = dict(balances)
    return {"annual": annual, "monthly": monthly,
            "retirement_balances": retirement_balances,
            "funded": first_shortfall is None, "first_shortfall": first_shortfall,
            "unfunded_expenses": cumulative_shortfall}


def sustainable_monthly_income(balances: dict[str, float], market_rate: float, months: int) -> float:
    """Largest constant monthly withdrawal funded across the entire horizon.

Uses the same proportional withdrawal policy as the projection, via bisection.
The amount includes principal drawdown and is not simply monthly interest.
"""
    if months <= 0:
        raise ValueError("Retirement horizon must be positive.")
    total = sum(balances.values())
    if total == 0:
        return 0.0
    rates = monthly_rates(market_rate)
    low, high = 0.0, total  # A start-of-month withdrawal cannot exceed the assets.
    for _ in range(55):
        trial = (low + high) / 2
        current = dict(balances)
        funded = True
        for _ in range(months):
            current, _, _, shortfall = retirement_month(current, rates, trial)
            if shortfall > 1e-8:
                funded = False
                break
        if funded:
            low = trial
        else:
            high = trial
    return low


def project_plan(plan: Plan, start_year: int) -> dict[str, dict]:
    return {scenario: project_scenario(plan, scenario, start_year) for scenario in SCENARIOS}
