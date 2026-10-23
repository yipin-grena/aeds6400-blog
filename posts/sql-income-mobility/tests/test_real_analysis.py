"""Synthetic-only checks of normalization and estimation.

These tests never open the PSID/FIMS workbooks or read any respondent records.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd


POST = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("real_analysis", POST / "real_analysis.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def invented_inputs():
    """Two invented waves and three invented people in one family."""
    waves = pd.DataFrame([
        dict(survey_year=1975, income_year=1974, interview="I75", sequence="S75",
             relation="R75", age="A75", income="Y75", rp_code=1, partner_codes="2;9",
             min_income=1, max_income=99999, exclude_one=1, topcode=99999),
        dict(survey_year=1994, income_year=1993, interview="I94", sequence="S94",
             relation="R94", age="A94", income="Y94", rp_code=10, partner_codes="20;22;90",
             min_income=-999999, max_income=9999998, exclude_one=0, topcode=np.nan),
    ])
    records = []
    for pn, sex, age75, sequence, relation75, relation94 in [
        (30, 1, 16, 3, 3, 30),
        (2, 2, 48, 2, 2, 20),
        (1, 1, 50, 1, 1, 10),
    ]:
        records.append(dict(
            ER30001=10, ER30002=pn, ER32000=sex, ER32006=1,
            I75=100, S75=sequence, R75=relation75, A75=age75, Y75=100,
            I94=100, S94=sequence, R94=relation94, A94=age75 + 19, Y94=600,
        ))
    fims = pd.DataFrame([
        dict(ID68=10, PN=30, ID68P=10, PNP=2, PTYPE="M"),
        dict(ID68=10, PN=30, ID68P=10, PNP=1, PTYPE="F"),
    ])
    cpi = pd.Series({1974: 50.0, 1993: 100.0, 2022: 200.0})
    return pd.DataFrame(records), fims, waves, cpi


class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.extract, self.fims, self.waves, self.cpi = invented_inputs()

    def normalize(self):
        return analysis.normalize(self.extract, self.fims, self.waves, self.cpi)

    def test_family_collapse_deflation_and_four_table_contract(self):
        tables, flow, audit = self.normalize()
        self.assertEqual(set(tables), {"people", "parent_links", "person_years", "family_years"})
        families = tables["family_years"].set_index("survey_year")
        self.assertEqual(len(families), 2)
        self.assertEqual(families.loc[1975, "income_year"], 1974)
        self.assertEqual(families.loc[1975, "family_income"], 400)
        self.assertEqual(families.loc[1994, "family_income"], 1200)
        self.assertEqual(flow.family_units.tolist(), [1, 1])
        self.assertEqual(flow.current_members.tolist(), [3, 3])
        self.assertEqual(audit["family_income_conflicts"], 0)
        with analysis.load_memory_database(tables) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM person_years").fetchone()[0], 6)
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_conflicting_repeated_family_income_fails_before_deduplication(self):
        self.extract.loc[1, "Y75"] = 999
        with self.assertRaisesRegex(ValueError, "Conflicting family incomes in wave 1975"):
            self.normalize()

    def test_historical_bottomcode_is_missing_but_documented_cap_is_retained(self):
        self.extract["Y75"] = 1
        tables, flow, _ = self.normalize()
        self.assertTrue(pd.isna(
            tables["family_years"].set_index("survey_year").loc[1975, "family_income"]
        ))
        self.assertEqual(flow.set_index("survey_year").loc[1975, "bottomcoded_income_excluded"], 1)
        self.extract["Y75"] = 99999
        tables, flow, _ = self.normalize()
        self.assertEqual(tables["family_years"].set_index("survey_year").loc[1975, "family_income"],
                         99999 * 4)
        self.assertEqual(flow.set_index("survey_year").loc[1975, "topcoded_income_retained_at_cap"], 1)

    def test_modern_missing_sentinel_is_not_a_large_valid_income(self):
        self.extract["Y94"] = 9999999
        tables, flow, _ = self.normalize()
        family = tables["family_years"].set_index("survey_year").loc[1994]
        self.assertTrue(pd.isna(family.family_income))
        self.assertTrue(pd.isna(family.family_income_nominal))
        self.assertEqual(flow.set_index("survey_year").loc[1994, "income_missing_or_out_of_range"], 1)

    def test_modern_negative_and_zero_income_are_not_removed(self):
        for amount in (-200, 0):
            with self.subTest(amount=amount):
                self.extract["Y94"] = amount
                tables, flow, _ = self.normalize()
                family = tables["family_years"].set_index("survey_year").loc[1994]
                self.assertEqual(family.family_income, amount * 2)
                self.assertEqual(family.family_income_nominal, amount)
                self.assertEqual(flow.set_index("survey_year").loc[1994, "valid_nonpositive_income"], 1)

    def test_prior_year_age_and_proxy_do_not_use_parent_age_for_child(self):
        tables, _, audit = self.normalize()
        people = tables["people"].set_index(["id68", "pn"])
        self.assertEqual(people.loc[(10, 30), "birth_year_proxy"], 1959)
        observations = tables["person_years"].set_index(["id68", "pn", "survey_year"])
        self.assertEqual(observations.loc[(10, 30, 1975), "income_age"], 15)
        self.assertEqual(observations.loc[(10, 2, 1975), "income_age"], 47)
        self.assertEqual(audit["people_with_birth_proxy_spread_over_two_years"], 0)

    def test_movers_are_not_current_members_and_role_requires_relationship_code(self):
        self.extract.loc[self.extract.ER30002.eq(2), "S94"] = 52
        self.extract.loc[self.extract.ER30002.eq(1), "R94"] = 30
        tables, flow, _ = self.normalize()
        observations = tables["person_years"]
        self.assertEqual(flow.set_index("survey_year").loc[1994, "current_members"], 2)
        self.assertFalse(((observations.pn == 2) & (observations.survey_year == 1994)).any())
        father = observations.loc[(observations.pn == 1) & (observations.survey_year == 1994)]
        self.assertEqual(father.is_reference_or_partner.iloc[0], 0)

    def test_missing_linked_parent_is_counted_without_creating_a_person(self):
        self.fims.loc[self.fims.PTYPE.eq("F"), ["ID68P", "PNP"]] = [99, 1]
        tables, _, audit = self.normalize()
        self.assertEqual(audit["fims_links_child_present"], 2)
        self.assertEqual(audit["fims_links_both_people_present"], 1)
        self.assertEqual(len(tables["people"]), 3)
        self.assertEqual(tables["parent_links"].parent_type.tolist(), ["M"])

    def test_duplicate_persons_are_rejected(self):
        self.extract = pd.concat([self.extract, self.extract.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate person keys"):
            self.normalize()


class EstimationTests(unittest.TestCase):
    def test_simple_slope_and_cluster_standard_error_match_independent_formulas(self):
        x = np.array([8., 9., 10., 11., 12., 13.])
        y = 0.8 + 0.6 * x + np.array([0.2, -0.1, 0.3, -0.2, -0.3, 0.1])
        groups = np.repeat(np.arange(3), 2)
        slope, se, clusters = analysis.slope_and_cluster_se(np.exp(x), np.exp(y), groups)
        expected_slope, intercept = np.polyfit(x, y, 1)
        residuals = y - (intercept + expected_slope * x)
        centered = x - x.mean()
        influence = np.array([np.sum(centered[groups == g] * residuals[groups == g])
                              for g in np.unique(groups)]) / np.sum(centered ** 2)
        expected_se = np.sqrt((3 / 2) * (5 / 4) * np.sum(influence ** 2))
        self.assertAlmostEqual(slope, expected_slope, places=12)
        self.assertAlmostEqual(se, expected_se, places=11)
        self.assertEqual(clusters, 3)

    def test_controls_recover_known_partial_slope(self):
        x = np.linspace(8, 12, 20)
        control = np.sin(np.arange(20))
        y = 1.5 + 0.7 * x - 0.4 * control
        slope, se, clusters = analysis.slope_and_cluster_se(
            np.exp(x), np.exp(y), np.repeat(np.arange(10), 2), control[:, None]
        )
        self.assertAlmostEqual(slope, 0.7, places=12)
        self.assertLess(se, 1e-10)
        self.assertEqual(clusters, 10)

    def test_rank_deficiency_and_single_cluster_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "rank deficient"):
            analysis.slope_and_cluster_se(np.ones(6), np.arange(1., 7.), np.repeat([0, 1, 2], 2))
        with self.assertRaisesRegex(ValueError, "Insufficient observations or clusters"):
            analysis.slope_and_cluster_se(np.arange(1., 7.), np.arange(2., 8.), np.zeros(6))

    def test_cluster_bootstrap_is_reproducible_and_paired(self):
        x = np.linspace(8, 12, 16)
        y = 0.4 + 0.6 * x + 0.05 * np.sin(np.arange(16))
        groups = np.repeat(np.arange(8), 2)
        models = {"first": (np.exp(x), np.exp(y)),
                  "identical": (np.exp(x), np.exp(y)),
                  "double_log_outcome": (np.exp(x), np.exp(2 * y))}
        first = analysis.bootstrap_slopes(models, groups, 200, seed=17)
        repeated = analysis.bootstrap_slopes(models, groups, 200, seed=17)
        np.testing.assert_array_equal(first, repeated)
        np.testing.assert_array_equal(first[:, 0], first[:, 1])
        np.testing.assert_allclose(first[:, 2], 2 * first[:, 0], atol=1e-10)
        # Directly rebuild the first five resampled datasets, rather than using
        # the implementation's cluster sufficient statistics.
        rng = np.random.default_rng(17)
        for b in range(5):
            selected_groups = rng.integers(0, 8, 8)
            positions = np.concatenate([np.flatnonzero(groups == g) for g in selected_groups])
            direct = np.polyfit(x[positions], y[positions], 1)[0]
            self.assertAlmostEqual(first[b, 0], direct, places=10)


class PublicInputTests(unittest.TestCase):
    def test_cpi_requires_complete_years_and_averages_months(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invented-cpi.csv"
            dates = pd.date_range("2022-01-01", periods=12, freq="MS")
            frame = pd.DataFrame({"DATE": dates, "CPIAUCNS": np.arange(100., 112.)})
            frame.to_csv(path, index=False)
            self.assertEqual(analysis.annual_cpi(path).loc[2022], 105.5)
            frame.iloc[:-1].to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "12 observations"):
                analysis.annual_cpi(path)

    def test_wave_timing_must_be_explicitly_prior_calendar_year(self):
        _, _, waves, _ = invented_inputs()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invented-waves.csv"
            waves.to_csv(path, index=False)
            self.assertEqual(len(analysis.read_waves(path)), 2)
            waves.loc[0, "income_year"] = 1975
            waves.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "Unexpected income timing"):
                analysis.read_waves(path)


if __name__ == "__main__":
    unittest.main()
