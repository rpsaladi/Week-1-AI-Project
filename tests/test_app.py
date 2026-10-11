import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"),
                                     default_timeout=30).run()

    def click(self, label):
        button = next(button for button in self.app.button if button.label == label)
        button.click().run(timeout=30)
        self.assertEqual(len(self.app.exception), 0)

    def test_empty_plan_requires_ages(self):
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(self.app.title[0].value, "Retirement")
        self.click("Save and view Analysis")
        self.assertTrue(self.app.error)
        self.assertIsNone(self.app.session_state["saved_plan"])

    def test_save_then_clear_resets_entire_plan(self):
        self.click("Try an example")
        self.click("Save and view Analysis")
        self.assertEqual(self.app.session_state["navigation"], "Analysis")
        self.assertEqual(self.app.session_state["saved_plan"].monthly_expenses, 4400)
        self.assertEqual(len(self.app.session_state["saved_results"]), 3)
        self.assertTrue(self.app.metric)
        self.click("Clear")
        self.assertIsNone(self.app.session_state["saved_plan"])
        self.assertIsNone(self.app.session_state["saved_results"])
        self.assertEqual(self.app.session_state["person_name"], "")
        self.assertIsNone(self.app.session_state["current_age"])
        self.assertIsNone(self.app.session_state["retirement_state"])
        self.assertEqual(self.app.session_state["account_base"]["Current Balance"].sum(), 0)
        self.assertEqual(self.app.session_state["expense_base"]["Amount"].sum(), 0)
        self.assertEqual(self.app.session_state["navigation"], "Your plan")

    def test_invalid_edit_keeps_saved_snapshot(self):
        self.click("Try an example")
        self.click("Save and view Analysis")
        saved = self.app.session_state["saved_plan"]
        self.app.number_input(key="current_age").set_value(70)
        self.click("Save and view Analysis")
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.session_state["saved_plan"], saved)

    def test_edit_without_saving_does_not_change_analysis(self):
        self.click("Try an example")
        self.click("Save and view Analysis")
        self.app.text_input(key="person_name").set_value("Edited").run()
        self.assertEqual(self.app.session_state["saved_plan"].name, "Alex")
        self.click("Save and view Analysis")
        self.assertEqual(self.app.session_state["saved_plan"].name, "Edited")

    def test_edited_table_cells_are_used_in_projection(self):
        self.click("Try an example")
        version = self.app.session_state["editor_version"]
        self.app.session_state[f"accounts_editor_{version}"] = {
            "edited_rows": {0: {"Current Balance": 300_000.0, "Contributions Yearly": 10_000.0}},
            "added_rows": [], "deleted_rows": [],
        }
        self.app.session_state[f"expenses_editor_{version}"] = {
            "edited_rows": {0: {"Amount": 1000.0}}, "added_rows": [], "deleted_rows": [],
        }
        self.click("Save and view Analysis")
        saved = self.app.session_state["saved_plan"]
        self.assertEqual(saved.balances["401 k"], 300_000)
        self.assertEqual(saved.contributions["401 k"], 10_000)
        self.assertEqual(saved.monthly_expenses, 2900)


if __name__ == "__main__":
    unittest.main()
