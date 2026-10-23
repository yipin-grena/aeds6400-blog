"""Exercise real-data matching SQL using invented records only.

Run with python -m unittest discover -s tests -p 'test_real_sql.py'.
No survey extract, private database, or saved respondent output is accessed.
"""
from pathlib import Path
import sqlite3
import unittest


POST = Path(__file__).resolve().parents[1]
SCHEMA = (POST / "sql/schema_real.sql").read_text()
QUERY = (POST / "sql/match_real.sql").read_text()
CHILD, MOTHER, FATHER = (10, 30), (10, 2), (10, 1)


class RealMatchingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.executemany(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?)",
            [(10, 30, 1, 1970, 1), (10, 2, 2, 1945, 1),
             (10, 1, 1, 1943, 1)],
        )
        self.conn.executemany(
            "INSERT INTO parent_links VALUES (?, ?, ?, ?, ?)",
            [(10, 30, 10, 2, "M"), (10, 30, 10, 1, "F")],
        )
        self.params = dict(
            birth_min=1960, birth_max=1978,
            p_start=15, p_end=19, p_min_obs=2, p_midpoint=17,
            c_start=40, c_end=44, c_min_obs=2, c_midpoint=42,
        )

    def family(self, survey_year, income, interview=100):
        # These invented incomes already represent constant 2022 dollars.
        self.conn.execute(
            "INSERT INTO family_years VALUES (?, ?, ?, ?, ?)",
            (survey_year, survey_year - 1, interview, income, income),
        )

    def member(self, person, survey_year, income_age, interview=100,
               reference=False, sequence=3):
        relation = (20 if sequence == 2 else 10) if reference else 30
        self.conn.execute(
            "INSERT INTO person_years VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*person, survey_year, interview,
             None if income_age is None else income_age + 1,
             income_age, sequence, relation, int(reference)),
        )

    def parental_year(self, survey_year, income, child_age,
                      both_parents=False, interview=100):
        self.family(survey_year, income, interview)
        self.member(CHILD, survey_year, child_age, interview)
        self.member(MOTHER, survey_year, child_age + 25, interview,
                    reference=True, sequence=2)
        if both_parents:
            self.member(FATHER, survey_year, child_age + 27, interview,
                        reference=True, sequence=1)

    def adult_year(self, survey_year, income, child_age, interview=100,
                   reference=True):
        self.family(survey_year, income, interview)
        self.member(CHILD, survey_year, child_age, interview,
                    reference=reference, sequence=1 if reference else 3)

    def basic_panel(self):
        # The first year has two linked parents; the second has only one
        # present. Failure to deduplicate would overweight the lower income.
        self.parental_year(1986, 100, 15, both_parents=True)
        self.parental_year(1988, 300, 17)
        self.adult_year(2011, 400, 40)
        self.adult_year(2013, 800, 42)

    def matched(self, **overrides):
        return self.conn.execute(QUERY, self.params | overrides).fetchall()

    def test_co_resident_parents_count_one_family_income_per_year(self):
        self.basic_panel()
        row, = self.matched()
        self.assertEqual(row["parent_income"], 200)
        self.assertEqual(row["parent_n"], 2)
        self.assertEqual(row["parent_mean_age"], 16)
        self.assertEqual(row["parent_single"], 300)
        self.assertEqual(row["parent_single_year"], 1987)
        self.assertEqual(row["child_income"], 600)
        self.assertEqual(row["child_n"], 2)
        self.assertEqual(row["child_single_year"], 2012)

    def test_separate_parent_family_is_not_added_to_child_resources(self):
        self.basic_panel()
        self.family(1988, 9000, interview=999)
        self.member(FATHER, 1988, 44, interview=999,
                    reference=True, sequence=1)
        row, = self.matched()
        self.assertEqual(row["parent_income"], 200)
        self.assertEqual(row["parent_n"], 2)

    def test_reused_interview_number_does_not_join_different_years(self):
        # Every family here intentionally reuses the same interview number.
        self.basic_panel()
        row, = self.matched()
        self.assertEqual(row["parent_first_year"], 1985)
        self.assertEqual(row["parent_last_year"], 1987)
        self.assertEqual(row["child_first_year"], 2010)
        self.assertEqual(row["child_last_year"], 2012)
        self.assertEqual(row["parent_income"], 200)
        self.assertEqual(row["child_income"], 600)

    def test_biennial_and_missing_observations_use_minimum_coverage(self):
        self.parental_year(1986, 100, 15)
        self.parental_year(1988, None, 17)
        self.parental_year(1990, 300, 19)
        self.adult_year(2011, 400, 40)
        self.adult_year(2013, 800, 42)
        row, = self.matched()
        self.assertEqual(row["parent_n"], 2)
        self.assertEqual(row["parent_income"], 200)
        self.assertEqual(row["parent_single_age"], 15)
        self.assertEqual(self.matched(p_min_obs=3), [])
        self.assertEqual(self.matched(c_min_obs=3), [])

    def test_valid_zero_and_negative_values_are_averaged_before_filtering(self):
        self.parental_year(1986, -100, 15)
        self.parental_year(1988, 300, 17)
        self.adult_year(2011, 0, 40)
        self.adult_year(2013, 400, 42)
        row, = self.matched(p_midpoint=15, c_midpoint=40)
        self.assertEqual(row["parent_income"], 100)
        self.assertEqual(row["child_income"], 200)
        # The caller chooses the common positive-single-observation sample.
        self.assertEqual(row["parent_single"], -100)
        self.assertEqual(row["child_single"], 0)

    def test_nonpositive_window_mean_is_excluded(self):
        self.basic_panel()
        self.conn.execute(
            "UPDATE family_years SET family_income = -100 WHERE survey_year < 2000"
        )
        self.assertEqual(self.matched(), [])

    def test_midpoint_ties_choose_earlier_income_year(self):
        self.parental_year(1986, 100, 15)
        self.parental_year(1990, 300, 19)
        self.adult_year(2011, 400, 40)
        self.adult_year(2015, 800, 44)
        row, = self.matched()
        self.assertEqual(row["parent_single"], 100)
        self.assertEqual(row["parent_single_age"], 15)
        self.assertEqual(row["parent_single_year"], 1985)
        self.assertEqual(row["child_single"], 400)
        self.assertEqual(row["child_single_age"], 40)
        self.assertEqual(row["child_single_year"], 2010)

    def test_birth_cohort_is_applied_to_children(self):
        self.basic_panel()
        self.assertEqual(len(self.matched(birth_min=1970, birth_max=1970)), 1)
        self.assertEqual(self.matched(birth_min=1971), [])
        self.conn.execute(
            "UPDATE people SET birth_year_proxy = NULL WHERE id68 = 10 AND pn = 30"
        )
        self.assertEqual(self.matched(), [])

    def test_adult_child_must_be_reference_person_or_partner(self):
        self.basic_panel()
        self.conn.execute(
            "UPDATE person_years SET is_reference_or_partner = 0 "
            "WHERE id68 = 10 AND pn = 30 AND survey_year = 2013"
        )
        self.assertEqual(self.matched(), [])

    def test_schema_rejects_movers_and_unmatched_identifiers(self):
        self.family(1986, 100)
        with self.assertRaises(sqlite3.IntegrityError):
            self.member(CHILD, 1986, 15, sequence=51)
        with self.assertRaises(sqlite3.IntegrityError):
            self.member((999, 30), 1986, 15)

    def test_result_contract_and_four_table_schema(self):
        self.basic_panel()
        row, = self.matched()
        self.assertEqual(row.keys(), [
            "id68", "pn", "birth_year_proxy", "parent_income", "parent_single",
            "parent_n", "parent_mean_age", "parent_single_age", "parent_single_year", "parent_first_year",
            "parent_last_year", "child_income", "child_single", "child_n",
            "child_mean_age", "child_single_age", "child_single_year", "child_first_year", "child_last_year",
        ])
        tables = {r[0] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
        self.assertEqual(tables, {"people", "parent_links", "family_years", "person_years"})


if __name__ == "__main__":
    unittest.main()
