import unittest
from dataclasses import replace

from retirement_model import (
    ACCOUNTS, CATEGORIES, SCENARIOS, STATES, Plan, monthly_rates,
    project_plan, project_scenario, sustainable_monthly_income, validate_plan,
)


def make_plan(**changes):
    plan = Plan("Test", 40, 42, 44, "New York",
                {account: 1000.0 for account in ACCOUNTS},
                {account: 100.0 for account in ACCOUNTS},
                {category: 10.0 for category in CATEGORIES})
    return replace(plan, **changes)


class ProjectionTests(unittest.TestCase):
    def test_annual_compounding_and_year_end_contributions(self):
        result = project_scenario(make_plan(), "Average market", 2026)
        for account in ACCOUNTS:
            rate = .03 if account == "HYSA" else .10
            expected = (1000 * (1 + rate) + 100) * (1 + rate) + 100
            self.assertAlmostEqual(result["retirement_balances"][account], expected)
        self.assertEqual(len(result["annual"]), 5)
        self.assertEqual(len(result["monthly"]), 48)
        self.assertEqual(result["annual"][-1]["Age"], 44)
        self.assertEqual(result["annual"][-1]["Year"], 2030)

    def test_monthly_rate_compounds_to_annual_rate(self):
        for market_rate in SCENARIOS.values():
            rates = monthly_rates(market_rate)
            self.assertAlmostEqual((1 + rates["Brokerage"]) ** 12, 1 + market_rate)
            self.assertAlmostEqual((1 + rates["HYSA"]) ** 12, 1.03)

    def test_retirement_starts_with_withdrawal_and_contributions_stop(self):
        result = project_scenario(make_plan(), "Average market", 2026)
        first = result["monthly"][24]
        self.assertEqual(first["Phase"], "Retirement")
        self.assertEqual(first["Expenses paid"], 40)
        self.assertEqual(first["Contributions"], 0)
        self.assertAlmostEqual(first["Closing assets"], first["Opening assets"] - 40 + first["Growth"])
        for account in ACCOUNTS:
            opening = result["retirement_balances"][account]
            fraction = 40 / first["Opening assets"]
            rate = monthly_rates(.10)[account]
            self.assertAlmostEqual(first[account], opening * (1 - fraction) * (1 + rate))

    def test_cash_flow_conservation_in_every_month(self):
        for result in project_plan(make_plan(), 2026).values():
            for row in result["monthly"]:
                self.assertAlmostEqual(row["Closing assets"], row["Opening assets"] + row["Growth"]
                                       + row["Contributions"] - row["Expenses paid"])
                self.assertAlmostEqual(row["Closing assets"], sum(row[account] for account in ACCOUNTS))

    def test_immediate_retirement_and_depletion(self):
        plan = make_plan(current_age=42, expenses={category: 1000.0 for category in CATEGORIES})
        result = project_scenario(plan, "Below-average market", 2026)
        self.assertEqual(result["retirement_balances"], plan.balances)
        self.assertEqual(result["monthly"][0]["Closing assets"], 0)
        self.assertEqual(result["monthly"][0]["Unfunded expenses"], 0)
        self.assertEqual(result["monthly"][1]["Unfunded expenses"], 4000)
        self.assertEqual(result["first_shortfall"]["Month"], 2)
        self.assertFalse(result["funded"])
        self.assertEqual(result["unfunded_expenses"], 23 * 4000)
        self.assertTrue(all(row["Contributions"] == 0 for row in result["monthly"]))

    def test_partial_withdrawal_has_visible_unfunded_budget(self):
        plan = make_plan(current_age=42, balances={account: 50.0 for account in ACCOUNTS},
                         expenses={category: 100.0 for category in CATEGORIES})
        result = project_scenario(plan, "Average market", 2026)
        self.assertEqual(result["monthly"][0]["Expenses paid"], 200)
        self.assertEqual(result["monthly"][0]["Unfunded expenses"], 200)
        self.assertEqual(result["monthly"][0]["Growth"], 0)
        self.assertTrue(all(row["Closing assets"] == 0 for row in result["monthly"]))

    def test_zero_assets_and_zero_expenses(self):
        plan = make_plan(current_age=42, balances={account: 0.0 for account in ACCOUNTS},
                         expenses={category: 0.0 for category in CATEGORIES})
        result = project_scenario(plan, "Average market", 2026)
        self.assertTrue(result["funded"])
        self.assertEqual(result["annual"][-1]["Assets"], 0)
        self.assertEqual(sustainable_monthly_income(plan.balances, .08, 24), 0)

    def test_hysa_only_is_identical_across_scenarios(self):
        plan = make_plan(balances={account: 10_000.0 if account == "HYSA" else 0.0 for account in ACCOUNTS},
                         contributions={account: 0.0 for account in ACCOUNTS})
        projections = project_plan(plan, 2026)
        totals = [result["annual"][-1]["Assets"] for result in projections.values()]
        self.assertEqual(totals[0], totals[1])
        self.assertEqual(totals[1], totals[2])

    def test_market_scenarios_are_ordered(self):
        projections = project_plan(make_plan(), 2026)
        totals = [result["annual"][-1]["Assets"] for result in projections.values()]
        self.assertGreater(totals[0], totals[1])
        self.assertGreater(totals[1], totals[2])

    def test_capacity_matches_closed_form_single_account_annuity_due(self):
        balances = {account: 12_000.0 if account == "HYSA" else 0.0 for account in ACCOUNTS}
        monthly_rate = 1.03 ** (1 / 12) - 1
        months = 360
        expected = 12_000 * monthly_rate / ((1 - (1 + monthly_rate) ** -months) * (1 + monthly_rate))
        capacity = sustainable_monthly_income(balances, .08, months)
        self.assertAlmostEqual(capacity, expected, places=6)

    def test_capacity_is_funded_and_larger_budget_is_not(self):
        plan = make_plan(current_age=42)
        capacity = sustainable_monthly_income(plan.balances, .08, 24)
        at_capacity = replace(plan, expenses={category: capacity / 4 for category in CATEGORIES})
        over_capacity = replace(plan, expenses={category: (capacity + 1) / 4 for category in CATEGORIES})
        self.assertTrue(project_scenario(at_capacity, "Below-average market", 2026)["funded"])
        self.assertFalse(project_scenario(over_capacity, "Below-average market", 2026)["funded"])

    def test_validation_rejects_bad_ages_and_nonfinite_money(self):
        self.assertTrue(validate_plan(make_plan(name=" ")))
        self.assertTrue(validate_plan(make_plan(current_age=45)))
        self.assertTrue(validate_plan(make_plan(plan_age=42)))
        self.assertTrue(validate_plan(make_plan(current_age=40.5)))
        self.assertTrue(validate_plan(make_plan(state="NY")))
        for value in (float("nan"), float("inf"), -1.0):
            balances = dict(make_plan().balances)
            balances["IRA"] = value
            self.assertTrue(validate_plan(make_plan(balances=balances)))
        with self.assertRaises(ValueError):
            project_scenario(make_plan(plan_age=42), "Average market", 2026)

    def test_all_50_states_are_available(self):
        self.assertEqual(len(STATES), 50)
        self.assertEqual(len(set(STATES)), 50)
        self.assertEqual(tuple(sorted(STATES)), STATES)


if __name__ == "__main__":
    unittest.main()
