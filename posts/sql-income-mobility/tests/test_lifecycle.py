"""Synthetic-only checks of the child single-observation lifecycle comparison.

No PSID/FIMS workbooks or respondent-level outputs are read or written.
"""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


POST = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("real_analysis_lifecycle", POST / "real_analysis.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def invented_lifecycle_panel(children=128):
    """Invent four matched windows, with two siblings per family of origin."""
    positions = np.arange(children)
    index = pd.MultiIndex.from_arrays(
        [10 + positions // 2, 30 + positions % 2], names=["id68", "pn"]
    )
    metadata = pd.DataFrame(
        {"birth_year_proxy": 1960 + positions % 17, "sex": 1 + positions % 2}, index=index
    )
    log_parent = np.linspace(8.0, 12.0, children)
    selected = {}
    for j, (start, end) in enumerate(analysis.AGE_WINDOWS):
        midpoint = (start + end) // 2
        single_age = midpoint + positions % 3 - 1
        single_log = 1.0 + (0.35 + 0.10 * j) * log_parent + 0.06 * np.sin(positions)
        average_log = 0.8 + (0.45 + 0.08 * j) * log_parent + 0.04 * np.cos(positions)
        selected[(start, end)] = pd.DataFrame(
            {
                "parent_income": np.exp(log_parent),
                # Deliberately different from the fixed parental average.
                "parent_single": np.exp(13.0 - 0.3 * log_parent),
                "parent_n": 3 + positions % 3,
                "parent_mean_age": 17.0,
                "parent_single_age": 17,
                "parent_single_year": metadata.birth_year_proxy + 17,
                "parent_first_year": metadata.birth_year_proxy + 15,
                "parent_last_year": metadata.birth_year_proxy + 19,
                "child_income": np.exp(average_log),
                "child_single": np.exp(single_log),
                "child_n": 2 + positions % 2,
                "child_mean_age": midpoint + 0.25,
                "child_single_age": single_age,
                "child_single_year": metadata.birth_year_proxy + single_age,
                "child_first_year": metadata.birth_year_proxy + start,
                "child_last_year": metadata.birth_year_proxy + end,
            },
            index=index,
        )
    return selected, metadata


def direct_slope(parent, child):
    """Independent centered-covariance calculation."""
    x = np.log(np.asarray(parent, dtype=float))
    y = np.log(np.asarray(child, dtype=float))
    return np.sum((x - x.mean()) * (y - y.mean())) / np.sum((x - x.mean()) ** 2)


def direct_paired_bootstrap(parent, outcomes, groups, repetitions=200):
    """Rebuild each resampled dataset, rather than group sufficient statistics."""
    labels = np.unique(groups)
    rng = np.random.default_rng(6400)
    draws = np.empty((repetitions, len(outcomes)))
    for b in range(repetitions):
        sampled = rng.integers(0, len(labels), len(labels))
        positions = np.concatenate([np.flatnonzero(groups == labels[g]) for g in sampled])
        for j, child in enumerate(outcomes):
            draws[b, j] = direct_slope(parent[positions], child[positions])
    return draws


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.selected, self.metadata = invented_lifecycle_panel()

    def run_lifecycle(self):
        return analysis.lifecycle_outputs(self.selected, self.metadata, 200)

    def test_fixed_parent_average_and_same_sample_for_all_eight_estimates(self):
        frames, audit = self.run_lifecycle()
        self.assertEqual(set(frames), {
            "lifecycle-estimates", "lifecycle-averages", "lifecycle-contrasts", "lifecycle-coverage"
        })
        self.assertEqual(audit["base_children"], 128)
        self.assertEqual(audit["children"], 128)
        self.assertEqual(audit["excluded_single_incomes"], 0)
        self.assertEqual(audit["origin_family_clusters"], 64)
        parent = self.selected[(40, 44)].parent_income.to_numpy()
        for frame_name, prefix, outcome in [
            ("lifecycle-estimates", "child_single", "child_single"),
            ("lifecycle-averages", "child_average", "child_income"),
        ]:
            frame = frames[frame_name].set_index("measure")
            self.assertEqual(set(frame.index), {
                f"{prefix}_age{start}_{end}" for start, end in analysis.AGE_WINDOWS
            })
            self.assertTrue(frame.children.eq(128).all())
            self.assertTrue(frame.origin_family_clusters.eq(64).all())
            for ages in analysis.AGE_WINDOWS:
                label = f"{prefix}_age{ages[0]}_{ages[1]}"
                child = self.selected[ages][outcome].to_numpy()
                self.assertAlmostEqual(frame.loc[label, "ige"], direct_slope(parent, child), places=11)
                controls = np.column_stack([
                    np.ones(len(parent)), np.log(parent),
                    self.metadata.birth_year_proxy.to_numpy() - 1969,
                    self.metadata.sex.eq(2).to_numpy(dtype=float),
                ])
                expected_adjusted = np.linalg.lstsq(controls, np.log(child), rcond=None)[0][1]
                self.assertAlmostEqual(frame.loc[label, "cohort_sex_adjusted_ige"],
                                       expected_adjusted, places=11)

    def test_nonpositive_and_nonfinite_singles_exclude_people_from_every_series(self):
        excluded = list(self.metadata.index[:4])
        for ages, key, bad in zip(analysis.AGE_WINDOWS, excluded, [0.0, -1.0, np.nan, np.inf]):
            self.selected[ages].loc[key, "child_single"] = bad
        frames, audit = self.run_lifecycle()
        self.assertEqual(audit["children"], 124)
        self.assertEqual(audit["excluded_single_incomes"], 4)
        keep = ~self.metadata.index.isin(excluded)
        parent = self.selected[(40, 44)].parent_income.to_numpy()[keep]
        for frame_name, prefix, column in [
            ("lifecycle-estimates", "child_single", "child_single"),
            ("lifecycle-averages", "child_average", "child_income"),
        ]:
            frame = frames[frame_name].set_index("measure")
            self.assertTrue(frame.children.eq(124).all())
            self.assertTrue(frame.origin_family_clusters.eq(62).all())
            for ages in analysis.AGE_WINDOWS:
                expected = direct_slope(parent, self.selected[ages][column].to_numpy()[keep])
                self.assertAlmostEqual(frame.loc[f"{prefix}_age{ages[0]}_{ages[1]}", "ige"],
                                       expected, places=11)
        self.assertTrue(frames["lifecycle-coverage"].children.eq(124).all())

    def test_paired_contrasts_match_direct_family_resampling(self):
        frames, _ = self.run_lifecycle()
        singles = frames["lifecycle-estimates"].set_index("measure")
        averages = frames["lifecycle-averages"].set_index("measure")
        all_estimates = pd.concat([singles, averages])
        labels = []
        outcomes = []
        for prefix, column in [("child_single", "child_single"), ("child_average", "child_income")]:
            for ages in analysis.AGE_WINDOWS:
                labels.append(f"{prefix}_age{ages[0]}_{ages[1]}")
                outcomes.append(self.selected[ages][column].to_numpy())
        parent = self.selected[(40, 44)].parent_income.to_numpy()
        groups = self.metadata.index.get_level_values("id68").to_numpy()
        draws = direct_paired_bootstrap(parent, outcomes, groups)
        expected_comparisons = [
            ("child_single_age40_44", "child_single_age25_29"),
            ("child_average_age40_44", "child_average_age25_29"),
        ] + [(f"child_average_age{a}_{b}", f"child_single_age{a}_{b}")
             for a, b in analysis.AGE_WINDOWS]
        contrasts = frames["lifecycle-contrasts"].set_index("comparison")
        self.assertEqual(set(contrasts.index), {f"{after} minus {before}"
                                               for after, before in expected_comparisons})
        for after, before in expected_comparisons:
            row = contrasts.loc[f"{after} minus {before}"]
            expected_difference = all_estimates.loc[after, "ige"] - all_estimates.loc[before, "ige"]
            self.assertAlmostEqual(row.ige_difference, expected_difference, places=11)
            expected_interval = np.quantile(draws[:, labels.index(after)] - draws[:, labels.index(before)],
                                            [0.025, 0.975])
            np.testing.assert_allclose([row.ci_lower, row.ci_upper], expected_interval, atol=1e-9, rtol=1e-9)

    def test_coverage_describes_selected_single_years_and_ages(self):
        frames, _ = self.run_lifecycle()
        coverage = frames["lifecycle-coverage"].set_index(["age_start", "age_end"])
        self.assertEqual(set(coverage.index), set(analysis.AGE_WINDOWS))
        for ages in analysis.AGE_WINDOWS:
            row = coverage.loc[ages]
            expected = self.selected[ages]
            self.assertEqual(row.min_selected_age, expected.child_single_age.min())
            self.assertEqual(row.mean_selected_age, expected.child_single_age.mean())
            self.assertEqual(row.max_selected_age, expected.child_single_age.max())
            self.assertEqual(row.first_income_year, expected.child_single_year.min())
            self.assertEqual(row.last_income_year, expected.child_single_year.max())

    def test_reordered_window_rows_are_aligned_to_person_keys(self):
        expected_frames, expected_audit = self.run_lifecycle()
        self.selected[(30, 34)] = self.selected[(30, 34)].iloc[::-1]
        frames, audit = self.run_lifecycle()
        self.assertEqual(audit, expected_audit)
        for name in frames:
            pd.testing.assert_frame_equal(frames[name], expected_frames[name])

    def test_different_parent_average_is_rejected(self):
        self.selected[(25, 29)].iloc[0, self.selected[(25, 29)].columns.get_loc("parent_income")] *= 2
        with self.assertRaisesRegex(ValueError, "[Pp]arent"):
            self.run_lifecycle()

    def test_fewer_than_100_common_positive_singles_is_rejected(self):
        self.selected[(25, 29)].loc[self.metadata.index[:29], "child_single"] = 0
        with self.assertRaisesRegex(ValueError, "100"):
            self.run_lifecycle()

    def test_saved_frames_contain_only_aggregate_results(self):
        frames, _ = self.run_lifecycle()
        private_columns = {"id68", "pn", "parent_income", "parent_single", "child_income", "child_single",
                           "birth_year_proxy", "sex"}
        for frame in frames.values():
            self.assertFalse(private_columns.intersection(frame.columns))
            self.assertNotIsInstance(frame.index, pd.MultiIndex)
            self.assertLessEqual(len(frame), 8)


if __name__ == "__main__":
    unittest.main()
