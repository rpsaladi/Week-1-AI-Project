# Retirement

A three-tab Streamlit retirement calculator with editable account and monthly expense
tables, in-memory saved plans, three fixed market scenarios, annual asset projections,
monthly retirement cash flow, downloadable CSVs, and an architecture and usage guide.

## Run locally

Use Python 3.11 or later. In PowerShell, from this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed by Streamlit (normally http://localhost:8501).
If your Python command is `python` instead of `py`, use that in the first line.
Use **Try an example**, then **Save and view Analysis**, for a quick demonstration.

## Model

- 401 k, IRA, and Brokerage: 10%, 8%, or 6% annually, according to scenario.
- HYSA: always 3% annually.
- Before retirement: compound monthly using equivalent annual rates; contributions
  arrive at each saving year end. Annual results equal `balance * (1 + rate) + contribution`.
- At retirement: contributions stop. The sum of monthly expenses is withdrawn at
  the start of each month, proportionally across accounts, before monthly growth.
- All balances stay non-negative; unmet spending is recorded separately.
- Plan-to-Age is an exclusive end boundary for monthly spending, and the annual
  table includes the final snapshot at that age.
- Monthly capacity is the highest constant withdrawal funded throughout retirement
  in the below-average scenario, using the same proportional withdrawal model.
- The status bar shows **scenario coverage**, not a probability. It is red for
  0 or 1 funded scenario, amber for 2, and green for all 3. A scenario is funded
  when it pays every monthly withdrawal to the nearest cent.
- Nominal dollars; no inflation, taxes, fees, benefits, market volatility, or
  account-specific legal rules. Retirement state is saved but does not affect calculations.
- Projection years start in the current America/New_York year. They are age-based
  planning periods, not exact birthdays or calendar-month cash flows.

## Files and validation

- `app.py`: Streamlit UI and session memory, pandas tables, Altair charts.
- `retirement_model.py`: pure Python calculations and validation.
- `tests/test_retirement_model.py`: numeric boundary and financial model tests.
- `tests/test_app.py`: Streamlit AppTest checks for save, reset, navigation, and validation.
- `.streamlit/config.toml`: application theme.
- [`docs/architecture.md`](docs/architecture.md): application flow, component responsibilities, state lifecycle, and projection assumptions.

Run checks after installing requirements:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

No database, persistent personal data storage, API key, or financial account connection
is required. Refreshing or ending a browser session can clear the saved plan.
