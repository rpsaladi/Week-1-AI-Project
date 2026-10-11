# Retirement App: Application and Architecture

## Overview

Retirement is a single-page Streamlit application for exploring a retirement
savings plan under three fixed-return scenarios. A user enters their ages,
retirement state, current account balances, annual contributions, and expected
monthly expenses. On save, the app validates the inputs, takes a plan snapshot,
calculates annual and monthly projections, and presents charts, tables, funding
indicators, and CSV downloads.

The app is an illustrative planning tool, not financial advice or a forecast.
It does not connect to financial accounts or external data services, and it
does not persist personal plans to a database.

## Architecture

```text
Browser
  │
  ▼
app.py — Streamlit form, session state, validation feedback, navigation
  │  validated Plan + projection start year
  ▼
retirement_model.py — deterministic calculations (no Streamlit or pandas)
  │  scenario results: annual rows, monthly rows, funding and shortfall details
  ▼
app.py — pandas tables/data shaping + Altair charts + CSV downloads
  │
  ▼
Browser
```

### Components

| Component | Responsibility |
| --- | --- |
| `app.py` | Defines the Streamlit page, profile form, example/reset actions, session-state lifecycle, validation feedback, analysis views, charts, and downloads. |
| `retirement_model.py` | Defines the `Plan` data structure, plan validation, monthly rates, account-level growth, retirement withdrawals, scenario projections, and sustainable monthly income. It is independently testable without the UI. |
| `tests/test_app.py` | Exercises UI behavior with Streamlit `AppTest`, including required inputs, saving, clearing, and preserving the saved snapshot until a valid resave. |
| `tests/test_retirement_model.py` | Verifies model inputs, monthly and annual timing, cash-flow conservation, depletion, scenario ordering, and withdrawal capacity. |
| `.streamlit/config.toml` | Sets the light theme and Streamlit server/browser defaults. |

The model uses only Python standard-library code. The UI uses Streamlit for
interaction, pandas for tables and CSV serialization, and Altair for charts.

## User flow and state

1. The **Your plan** tab collects name, current age, retirement age, Plan-to-Age,
   retirement state, balances, contributions, and monthly expenses.
2. The account and expense tables have fixed rows. The model requires all four
   accounts (`401 k`, `IRA`, `Brokerage`, `HYSA`) and all four expense categories
   (`Housing`, `Food`, `Health`, `Travel`).
3. Selecting **Save and view Analysis** constructs a `Plan` from the form and
   table values. `validate_plan` checks the name, whole-number age bounds and
   ordering, state, required categories, and finite non-negative amounts.
4. A valid plan is projected for all three scenarios. The saved plan, results,
   monthly capacity, and projection start year are held in Streamlit session
   state; the app then navigates to **Analysis**.
5. Analysis renders the saved snapshot. Editing the form does not silently
   change the analysis; the user must save again. Invalid input leaves the
   prior saved snapshot intact.
6. **Try an example** fills in an illustrative plan and clears any prior saved
   analysis. **Clear** resets the inputs and saved analysis. Editor widget keys
   are versioned on reset so old table-edit deltas do not repopulate cleared
   values.

Streamlit reruns the script as widgets change. The app renders each top-level
tab on each run and gates the projection calculation on the save action, so
navigation preserves form widget state without recalculating a plan on every
edit. Session state is temporary: refreshing or ending the browser session may
discard the plan.

## Projection model

### Inputs and assumptions

- Market accounts (`401 k`, `IRA`, and `Brokerage`) use the selected annual
  scenario rate: 10% (average), 8% (below average), or 6% (significantly below
  average).
- `HYSA` always uses a 3% annual rate.
- Annual returns are converted to equivalent monthly rates:
  `monthly_rate = (1 + annual_rate) ** (1 / 12) - 1`.
- Expenses are a combined monthly budget. The state is stored with the plan but
  does not affect calculations.
- Amounts are nominal. The model excludes inflation, taxes, fees, benefits,
  market volatility, and account-specific legal rules.

### Saving phase

Each account compounds monthly until retirement. At the end of each saving
year, the annual contribution for that account is added. Contributions stop
when retirement begins. For an account with annual return `r`, opening annual
balance `B`, and annual contribution `C`, the year-end balance is:

```text
B_next = B * (1 + r) + C
```

The current projection year is obtained using the `America/New_York` time zone.
Projection months are age-based planning periods, not exact birthdays or
calendar-month cash flows.

### Retirement phase

At the start of each retirement month, the model withdraws up to the full
monthly budget from total assets. The withdrawal is allocated proportionally
across the account balances. The remaining balance in each account then grows
at its monthly rate. If the assets cannot cover the budget, the unpaid amount
is recorded as an unfunded expense; balances do not become negative.

The Plan-to-Age is the exclusive end boundary for monthly projection: a plan
from age 65 through age 95 models 360 months. The annual output includes a
snapshot at the final age. The retirement-age snapshot is before the first
retirement withdrawal, while the final-age snapshot includes all modeled
withdrawals.

### Scenario status and monthly capacity

A scenario is marked funded if no monthly shortfall exceeds half a cent. The
analysis reports how many of the three scenarios fund the plan. The red,
amber, and green status bands are a deterministic comparison, not a probability
of success; no likelihood is assigned to the scenarios.

Monthly capacity is calculated using the below-average (8%) scenario. A
bisection search finds the largest constant start-of-month withdrawal that
remains funded for every month of the retirement horizon. This includes
principal drawdown; it is not interest-only income.

## Analysis outputs

- **Summary metrics:** current assets, yearly contributions, and monthly
  retirement expenses.
- **Funding summary:** count of scenarios that fully pay the monthly budget,
  below-average first-shortfall details, and monthly capacity compared with the
  entered budget.
- **Annual projection:** total assets by scenario, with a retirement marker,
  plus account-level balances.
- **Monthly retirement cash flow:** opening assets, growth, expenses paid,
  unfunded expenses, and closing assets by month and scenario.
- **Downloads:** yearly projection as `retirement_yearly.csv` and monthly cash
  flow as `retirement_monthly.csv`.

## Running and testing

From the repository root, create the environment, install the pinned/ranged
dependencies, and run the app:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Run the unit and Streamlit app tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
