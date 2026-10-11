"""Retirement: run with `python -m streamlit run app.py`."""

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

from retirement_model import (
    ACCOUNTS, CATEGORIES, SCENARIOS, STATES, Plan, project_plan,
    sustainable_monthly_income, validate_plan,
)


st.set_page_config(page_title="Retirement", page_icon="🌱", layout="wide")
COLORS = ["#3984F5", "#2854B7", "#273655"]
MONEY = st.column_config.NumberColumn(format="dollar", width="medium")

st.html("""
<style>
.block-container { max-width: 1240px; padding-top: 2.4rem; padding-bottom: 3rem; }
h1, h2, h3 { letter-spacing: -.035em; }
h1 { font-size: 3.3rem !important; font-weight: 750 !important; }
[data-testid="stCaptionContainer"] { color: #64748b; }
[data-testid="stMetric"] { background: white; border: 1px solid #e1e7ef;
  padding: 20px; border-radius: 14px; }
[data-testid="stMetricValue"] { font-size: 1.8rem; }
[data-baseweb="tab-list"] { gap: 26px; }
[data-baseweb="tab"] { font-weight: 600; }
[data-testid="stForm"] { border: 0; padding: 0; }
.eyebrow { color: #0d8274; font-size: .78rem; font-weight: 700;
  letter-spacing: .15em; margin-bottom: .45rem; }
.step { display: inline-flex; background: #e5f3ef; color: #0d8274; width: 26px;
  height: 26px; border-radius: 7px; align-items: center; justify-content: center;
  font-size: .9rem; margin-right: 9px; vertical-align: middle; }
.field-label { padding-top: 9px; font-size: .94rem; font-weight: 500; }
.note { padding: 20px; background: #edf5f3; border-radius: 12px;
  color: #355b55; line-height: 1.7; }
.st-key-guide_content [data-testid="stMarkdownContainer"] { overflow-wrap: anywhere; }
.st-key-guide_content .katex-display { max-width: 100%; overflow-x: auto; overflow-y: hidden; }
.guide-rates { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 14px; margin-bottom: 20px; }
.guide-rate { min-width: 0; padding: 18px; border: 1px solid #e1e7ef; border-radius: 12px;
  background: #fff; line-height: 1.7; overflow-wrap: anywhere; }
.guide-rate strong { display: block; margin-bottom: 8px; }
</style>
""")


def account_data(example=False):
    return pd.DataFrame({
        "Account": ACCOUNTS,
        "Current Balance": [250_000., 60_000., 40_000., 15_000.] if example else [0.] * 4,
        "Contributions Yearly": [23_000., 7_000., 6_000., 1_000.] if example else [0.] * 4,
    })


def expense_data(example=False):
    return pd.DataFrame({"Category": CATEGORIES,
                         "Amount": [2_500., 650., 750., 500.] if example else [0.] * 4})


def reset_inputs(example=False):
    st.session_state.update({
        "person_name": "Alex" if example else "",
        "current_age": 40 if example else None,
        "retirement_age": 65 if example else None,
        "plan_age": 95 if example else None,
        "retirement_state": "North Carolina" if example else None,
        "account_base": account_data(example), "expense_base": expense_data(example),
        "editor_version": st.session_state.get("editor_version", 0) + 1,
        "saved_plan": None, "saved_results": None, "navigation": "Your plan",
    })
    # Editors store deltas. A fresh key prevents cleared values from reappearing.
    for key in list(st.session_state):
        if key.startswith(("accounts_editor_", "expenses_editor_")):
            del st.session_state[key]


if "editor_version" not in st.session_state:
    reset_inputs()
if "pending_navigation" in st.session_state:
    st.session_state.navigation = st.session_state.pop("pending_navigation")


def money(value):
    return f"${value:,.0f}"


def section(number, title):
    st.html(f'<h3><span class="step">{number}</span>{escape(title)}</h3>')


def scenario_status_bar(funded_count):
    """Show a read-only status marker in the appropriate funding band."""
    status, color = (
        ("Red", "#B42332") if funded_count <= 1 else
        ("Amber", "#835700") if funded_count == 2 else
        ("Green", "#17653C")
    )
    position = {0: 8.33, 1: 25, 2: 50, 3: 83.33}[funded_count]
    st.html(f"""
    <div style="margin:8px 0 20px">
      <div style="font-weight:700;color:{color};margin-bottom:16px">
        {status} · {funded_count} of 3 scenarios funded
      </div>
      <div role="meter" aria-label="Retirement scenario funding"
        aria-valuemin="0" aria-valuemax="3" aria-valuenow="{funded_count}"
        aria-valuetext="{status}: {funded_count} of 3 scenarios funded"
        style="position:relative;height:18px;border-radius:9px;
          background:linear-gradient(to right,#C53E3E 0%,#C53E3E 33.33%,
          #E5AC32 33.33%,#E5AC32 66.67%,#268452 66.67%,#268452 100%)">
        <div style="position:absolute;left:{position}%;top:-6px;width:14px;height:30px;
          transform:translateX(-50%);background:#172B46;border:3px solid white;
          border-radius:7px;box-sizing:border-box;box-shadow:0 1px 4px #172B4640"></div>
      </div>
      <div style="display:flex;margin-top:10px;font-size:.85rem;line-height:1.5;color:#172B46">
        <span style="flex:1;text-align:center;padding:0 4px">Red · 0–1 of 3</span>
        <span style="flex:1;text-align:center;padding:0 4px">Amber · 2 of 3</span>
        <span style="flex:1;text-align:center;padding:0 4px">Green · 3 of 3</span>
      </div>
    </div>
    """)


def scenario_color():
    return alt.Color("Scenario:N", scale=alt.Scale(domain=list(SCENARIOS), range=COLORS),
                     legend=alt.Legend(title=None, orient="bottom"))


def render_profile():
    st.subheader("Build your retirement plan")
    st.caption("A few details today. A clearer picture of tomorrow. All amounts are in US dollars.")
    st.button("Try an example", on_click=reset_inputs, args=(True,))
    with st.form("profile_form"):
        with st.container(border=True):
            section(1, "Profile")
            fields, context = st.columns([1.6, 1], gap="large")
            with fields:
                for label, key in [("Name", "person_name"), ("Current Age", "current_age"),
                                   ("Age of Retirement", "retirement_age"), ("Plan-to-Age", "plan_age"),
                                   ("Retirement State", "retirement_state")]:
                    text, control = st.columns([1, 1.7])
                    with text:
                        st.html(f'<div class="field-label">{label}</div>')
                    with control:
                        if key == "person_name":
                            st.text_input(label, key=key, label_visibility="collapsed", placeholder="Your name")
                        elif key == "retirement_state":
                            st.selectbox(label, STATES, index=None, key=key,
                                         label_visibility="collapsed", placeholder="Select a state")
                        else:
                            st.number_input(label, min_value=18, max_value=120, value=None,
                                            step=1, key=key, label_visibility="collapsed", placeholder="Age")
            with context:
                st.html('<div class="note"><b>Your planning horizon</b><br>'
                        'Current age starts the projection. Retirement age marks when contributions '
                        'stop and monthly spending begins. Plan-to-Age sets the end of the projection.'
                        '<br><br>Your state is saved with your profile. This model does not calculate state taxes.</div>')
        # Give each editable table the full form width, including on smaller screens.
        with st.container(border=True):
            section(2, "Accounts and Contributions")
            st.caption("Current savings and the amount you add each year before retirement.")
            accounts = st.data_editor(
                st.session_state.account_base,
                key=f"accounts_editor_{st.session_state.editor_version}",
                hide_index=True, num_rows="fixed", disabled=["Account"], width="stretch",
                column_config={
                    "Account": st.column_config.TextColumn(width="small"),
                    "Current Balance": st.column_config.NumberColumn(min_value=0., max_value=1e12,
                                                                      format="dollar", required=True),
                    "Contributions Yearly": st.column_config.NumberColumn(min_value=0., max_value=1e12,
                                                                           format="dollar", required=True),
                },
            )
        with st.container(border=True):
            section(3, "Expenses in Retirement")
            st.write("Enter monthly spending for each category in **US dollars**.")
            expenses = st.data_editor(
                st.session_state.expense_base,
                key=f"expenses_editor_{st.session_state.editor_version}",
                hide_index=True, num_rows="fixed", disabled=["Category"], width="stretch",
                row_height=42,
                column_config={"Category": st.column_config.TextColumn(width=100),
                               "Amount": st.column_config.NumberColumn(width=180, min_value=0., max_value=1e12,
                                                                        format="dollar", required=True)},
            )
        save_col, clear_col, _ = st.columns([2, 1, 3])
        with save_col:
            save = st.form_submit_button("Save and view Analysis", type="primary", width="stretch")
        with clear_col:
            st.form_submit_button("Clear", on_click=reset_inputs, width="stretch")
        st.caption("Saved in this browser session's memory. Refreshing or ending the session may reset your plan.")
    if save:
        if any(st.session_state[key] is None for key in ("current_age", "retirement_age", "plan_age")):
            st.error("Enter your current age, retirement age, and Plan-to-Age.")
            return
        try:
            plan = Plan(
                name=st.session_state.person_name.strip(), current_age=st.session_state.current_age,
                retirement_age=st.session_state.retirement_age, plan_age=st.session_state.plan_age,
                state=st.session_state.retirement_state,
                balances=dict(zip(accounts.Account, accounts["Current Balance"].astype(float))),
                contributions=dict(zip(accounts.Account, accounts["Contributions Yearly"].astype(float))),
                expenses=dict(zip(expenses.Category, expenses.Amount.astype(float))),
            )
            errors = validate_plan(plan)
        except (TypeError, ValueError):
            st.error("Complete all balance, contribution, and expense cells with non-negative numbers.")
            return
        if errors:
            for error in errors:
                st.error(error)
            return
        start_year = datetime.now(ZoneInfo("America/New_York")).year
        results = project_plan(plan, start_year)
        below = results["Below-average market"]
        capacity = sustainable_monthly_income(below["retirement_balances"], 0.08,
                                               (plan.plan_age - plan.retirement_age) * 12)
        st.session_state.update(saved_plan=plan, saved_results=results,
                                monthly_capacity=capacity, start_year=start_year,
                                pending_navigation="Analysis", just_saved=True)
        st.rerun()


def render_analysis():
    plan = st.session_state.saved_plan
    if plan is None:
        st.info("Enter your profile, accounts, and expenses in Your plan, then select Save and view Analysis.")
        return
    results = st.session_state.saved_results
    start_year = st.session_state.start_year
    retirement_year = start_year + plan.retirement_age - plan.current_age
    if st.session_state.pop("just_saved", False):
        st.success("Plan saved. This analysis uses your saved inputs.")
    st.subheader(f"{plan.name}'s retirement outlook")
    st.caption(f"{plan.state} · Retire at {plan.retirement_age} · Plan through age {plan.plan_age} · "
               "Return to Your plan and save again to apply changes.")
    a, b, c = st.columns(3)
    a.metric("Current assets", money(sum(plan.balances.values())))
    b.metric("Yearly contributions", money(sum(plan.contributions.values())))
    c.metric("Monthly retirement expenses", money(plan.monthly_expenses))

    with st.container(border=True):
        st.subheader("How are you doing?")
        funded_count = sum(result["funded"] for result in results.values())
        scenario_status_bar(funded_count)
        st.markdown(f"**{funded_count} of 3 market scenarios fund your full retirement.**")
        capacity = st.session_state.monthly_capacity
        gap = capacity - plan.monthly_expenses
        if gap >= -0.005:
            summary = (f"In a below-average market, your assets could support about {money(capacity)} "
                       f"per month through age {plan.plan_age}, or {money(max(0, gap))} more than "
                       f"your {money(plan.monthly_expenses)} monthly budget.")
        else:
            summary = (f"In a below-average market, your assets could support about {money(capacity)} "
                       f"per month through age {plan.plan_age}. Your {money(plan.monthly_expenses)} "
                       f"monthly budget exceeds that by {money(-gap)}.")
        # Dollar signs in prose are currency, not Markdown math delimiters.
        st.markdown(summary.replace("$", r"\$"))
        shortfall = results["Below-average market"]["first_shortfall"]
        if shortfall:
            st.warning(f"The below-average plan first cannot pay the full budget at age "
                       f"{shortfall['Age']:.1f} (projection year {shortfall['Year']}).")
        st.caption("Scenario coverage is a deterministic stress check, not a probability of success. "
                   "Monthly capacity includes spending down principal; it is not interest-only income.")

    st.subheader("Asset projection")
    st.caption("Projected dollars, with fixed returns and no inflation adjustment. "
               "The retirement marker shows when spending begins. Areas overlap; they are not added together.")
    annual = pd.DataFrame([row for result in results.values() for row in result["annual"]])
    chart_tab, table_tab = st.tabs(["Chart", "Table"])
    with chart_tab:
        base = alt.Chart(annual).encode(
            x=alt.X("Year:Q", axis=alt.Axis(format="d", tickMinStep=1), title="Projection year",
                    scale=alt.Scale(zero=False)),
            y=alt.Y("Assets:Q", title="Total assets", axis=alt.Axis(format="$.2s")),
            color=scenario_color(),
            tooltip=[alt.Tooltip("Scenario:N"), alt.Tooltip("Year:Q", format="d"),
                     alt.Tooltip("Age:Q", format="d"), alt.Tooltip("Assets:Q", format="$,.0f")],
        )
        area = base.mark_area(opacity=0.24).encode(order=alt.Order("Scenario:N", sort="ascending"))
        lines = base.mark_line(strokeWidth=2.5)
        marker_data = pd.DataFrame({"Year": [retirement_year], "Label": ["Retirement"]})
        marker = alt.Chart(marker_data).mark_rule(color="#172B46", strokeDash=[5, 4]).encode(x="Year:Q")
        label = alt.Chart(marker_data).mark_text(align="left", dx=8, dy=10, baseline="top",
                                                color="#172B46").encode(x="Year:Q", y=alt.value(0), text="Label:N")
        chart = (area + lines + marker + label).properties(height=350).configure_view(stroke=None)
        st.altair_chart(chart, width="stretch")
    annual_wide = annual.pivot(index=["Year", "Age"], columns="Scenario", values="Assets").reset_index()
    annual_wide = annual_wide[["Year", "Age", *SCENARIOS]]
    with table_tab:
        st.caption("Age-boundary snapshots: the retirement row is before the first withdrawal; "
                   "the final row includes all spending up to Plan-to-Age.")
        st.dataframe(annual_wide, hide_index=True, width="stretch",
                     column_config={scenario: MONEY for scenario in SCENARIOS})
        st.download_button("Download yearly projection", annual_wide.to_csv(index=False),
                           "retirement_yearly.csv", "text/csv")
    st.markdown("**Assets at end of plan**")
    for column, scenario in zip(st.columns(3), reversed(SCENARIOS)):
        column.metric(scenario, money(results[scenario]["annual"][-1]["Assets"]))

    st.subheader("Monthly retirement cash flow")
    st.caption("Growth is earned after each month's withdrawal. Unfunded expenses remain visible "
               "when assets run out. Projection months are relative to your age, not calendar dates.")
    monthly = pd.DataFrame([row for result in results.values() for row in result["monthly"]
                            if row["Phase"] == "Retirement"])
    monthly_chart_tab, monthly_table_tab = st.tabs(["Monthly chart", "Monthly table"])
    with monthly_chart_tab:
        growth_chart = alt.Chart(monthly).mark_line(strokeWidth=2).encode(
            x=alt.X("Age:Q", scale=alt.Scale(zero=False), title="Age at start of month"),
            y=alt.Y("Growth:Q", title="Monthly investment growth", axis=alt.Axis(format="$.2s")),
            color=scenario_color(), tooltip=["Scenario:N", alt.Tooltip("Age:Q", format=".2f"),
                                            alt.Tooltip("Growth:Q", format="$,.2f")],
        )
        budget = alt.Chart(pd.DataFrame({"Budget": [plan.monthly_expenses]})).mark_rule(
            strokeDash=[5, 4], color="#B44B48").encode(y="Budget:Q")
        st.altair_chart((growth_chart + budget).properties(height=270).configure_view(stroke=None),
                        width="stretch")
        st.caption(f"Dashed red line: your {money(plan.monthly_expenses)} monthly budget. "
                   "Growth below spending can still fund a plan by drawing down principal.")
    with monthly_table_tab:
        display_cols = ["Projection month", "Year", "Age", "Scenario", "Opening assets", "Growth",
                        "Expenses paid", "Unfunded expenses", "Closing assets"]
        monthly_display = monthly[display_cols].sort_values(["Projection month", "Scenario"])
        st.dataframe(monthly_display, hide_index=True, width="stretch",
                     column_config={**{column: MONEY for column in display_cols[4:]},
                                    "Age": st.column_config.NumberColumn(format="%.2f")})
        st.download_button("Download monthly cash flow", monthly.to_csv(index=False),
                           "retirement_monthly.csv", "text/csv")
    with st.expander("Account balances and scenario funding details"):
        st.dataframe(annual[["Year", "Age", "Scenario", *ACCOUNTS]], hide_index=True,
                     width="stretch", column_config={account: MONEY for account in ACCOUNTS})
        funding = pd.DataFrame([
            {"Scenario": scenario, "Fully funded": result["funded"],
             "Total unfunded expenses": result["unfunded_expenses"]}
            for scenario, result in results.items()
        ])
        st.dataframe(funding, hide_index=True, width="stretch",
                     column_config={"Total unfunded expenses": MONEY})


def render_guide():
    st.subheader("A clear plan, from inputs to insights")
    st.caption("How to use Retirement and how the calculations work.")
    # Stack the guide sections so text and diagrams have room at every screen width.
    with st.container(border=True):
        st.markdown("### How to use the app")
        st.markdown("""
1. Enter your name, ages, and retirement state in **Your plan**.
2. Add current balances and yearly contributions for all four accounts.
3. Enter **monthly** Housing, Food, Health, and Travel expenses. Zero is allowed.
4. Select **Save and view Analysis** to save a snapshot in session memory and open Analysis.
5. Compare the three scenarios in the chart, annual table, and monthly cash flow.
6. Edit your inputs and save again to update the results. **Clear** removes inputs and the saved analysis.

**Try an example** fills the form with an illustrative plan and clears any previous saved analysis.
Save it to see its results. Name and state stay in your browser session; the app uses no database.
""")
    with st.container(border=True):
        st.markdown("### Architecture")
        st.code("Streamlit input form\n        ↓ validate + save\nSession State: immutable plan snapshot\n        ↓\nPure Python projection engine\n        ↓\nAnnual + monthly rows for 3 scenarios\n        ↓\nAltair charts · pandas tables · funding KPI", language="text", wrap_lines=True)
        st.markdown("**app.py** handles forms, navigation, in-memory state, and charts. "
                    "**retirement_model.py** handles validation, compound growth, withdrawals, "
                    "depletion, and sustainable monthly spending. The model can be tested without the UI.")
    with st.container(border=True):
        st.markdown("### Calculation assumptions")
        # Wrapping cards keep long scenario names and account labels visible on narrow screens.
        rate_cards = "".join(
            f'<div class="guide-rate"><strong>{escape(scenario)}</strong>'
            f'<div>401 k / IRA / Brokerage: <b>{rate:.0%} per year</b></div>'
            '<div>HYSA: <b>3% per year</b></div></div>'
            for scenario, rate in SCENARIOS.items()
        )
        st.html(f'<div class="guide-rates">{rate_cards}</div>')
        st.markdown("""
Before retirement, each account grows monthly at an equivalent annual rate. Yearly contributions
are deposited at the end of each saving year, including the last year before retirement.
This gives the annual recurrence below. Contributions stop when retirement starts.
""")
        st.latex(r"B_{y+1} = B_y(1+r) + C")
        st.latex(r"r_m = (1+r)^{1/12}-1")
        st.markdown("**B** is the account balance, **r** is the annual growth rate, "
                    "**C** is the yearly contribution, and **rₘ** is the equivalent monthly growth rate.")
        st.markdown("""
In retirement, the combined monthly budget is withdrawn **at the start of each month**,
proportionally from all accounts. Each remaining balance then earns its monthly return.
Balances are capped at zero, and any unpaid budget is recorded as unfunded expenses.
The projection stops at the Plan-to-Age boundary: retiring at 65 and planning to 95 models 360 months.

**Monthly capacity** finds the highest constant monthly withdrawal that the below-average
scenario can fund over the entire retirement horizon. It uses the same withdrawal policy
and includes spending down principal. **Scenario coverage** is the percentage of the three
fixed scenarios that pay every monthly budget in full (to the nearest cent).
The status bar is red for 0 or 1 funded scenario, amber for 2, and green for all 3.
These scenarios have no assigned likelihood, so this is not a statistical probability.

Amounts are nominal projected dollars. There is no inflation, tax, fee, Social Security,
pension, contribution-limit enforcement, required distribution, or market volatility calculation.
The retirement state is descriptive and does not affect the projections. The supplied growth
rates are assumptions, not forecasts. This is an illustrative planning calculator.
""")
    st.caption("Built with Streamlit, pandas, and Altair. No external financial data or account connections.")


st.html('<div class="eyebrow">YOUR NEXT CHAPTER</div>')
st.title("Retirement")
st.write("Plan with perspective. See how your savings can support the life ahead.")
profile_tab, analysis_tab, guide_tab = st.tabs(
    ["Your plan", "Analysis", "Architecture & Guide"], key="navigation", on_change="rerun"
)
# Render every tab so form widget state survives navigation; calculations run only on save.
with profile_tab:
    render_profile()
with analysis_tab:
    render_analysis()
with guide_tab:
    with st.container(key="guide_content"):
        render_guide()
st.divider()
st.caption("RETIREMENT · Your plan stays in session memory · Fixed-rate projections")
