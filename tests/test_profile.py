import unittest

from engine.domain.profile import build_profile


def _prices(counts: list[int], bin_size: float) -> list[float]:
    prices: list[float] = []
    for index, count in enumerate(counts):
        prices.extend([(index + 0.5) * bin_size] * count)
    return prices


class ProfileTests(unittest.TestCase):
    def test_worked_example_from_spec(self) -> None:
        bin_size = 0.0005
        prices = _prices([2, 5, 12, 25, 18, 10, 6, 3], bin_size)

        profile = build_profile(
            prices,
            bin_size=bin_size,
            value_area_target=0.70,
            tail_bins=3,
            single_print_max_ticks=1,
            min_ticks=30,
            current_price=3.5 * bin_size,
        )

        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.total_ticks, 81)
        self.assertEqual(profile.poc_bin, 3)
        self.assertEqual(profile.val_bin, 1)
        self.assertEqual(profile.vah_bin, 5)
        self.assertAlmostEqual(profile.val, 1 * bin_size)
        self.assertAlmostEqual(profile.vah, 6 * bin_size)
        self.assertEqual(profile.value_area_ticks, 70)
        self.assertAlmostEqual(profile.value_area_share, 70 / 81)
        self.assertEqual(profile.tail_length_high, 2)
        self.assertEqual(profile.tail_length_low, 1)

    def test_poc_tie_break_prefers_nearest_bin(self) -> None:
        bin_size = 0.001
        prices = [0.00025] * 5 + [0.00125] * 5

        nearest_upper = build_profile(
            prices,
            bin_size=bin_size,
            value_area_target=0.70,
            tail_bins=2,
            single_print_max_ticks=1,
            min_ticks=1,
            current_price=0.0012,
        )
        assert nearest_upper is not None
        self.assertEqual(nearest_upper.poc_bin, 1)

    def test_poc_tie_break_prefers_lower_bin_when_equidistant(self) -> None:
        bin_size = 0.001
        prices = [0.00025] * 5 + [0.00125] * 5

        equidistant = build_profile(
            prices,
            bin_size=bin_size,
            value_area_target=0.70,
            tail_bins=2,
            single_print_max_ticks=1,
            min_ticks=1,
            current_price=0.0010,
        )
        assert equidistant is not None
        self.assertEqual(equidistant.poc_bin, 0)

    def test_insufficient_ticks_returns_none(self) -> None:
        profile = build_profile(
            [0.0001, 0.0002, 0.0003],
            bin_size=0.001,
            value_area_target=0.70,
            tail_bins=2,
            single_print_max_ticks=1,
            min_ticks=5,
            current_price=0.0002,
        )
        self.assertIsNone(profile)

    def test_single_bin_uses_full_bin_edges(self) -> None:
        bin_size = 0.001
        profile = build_profile(
            [0.0007] * 4,
            bin_size=bin_size,
            value_area_target=0.70,
            tail_bins=2,
            single_print_max_ticks=1,
            min_ticks=1,
            current_price=0.0007,
        )
        assert profile is not None
        self.assertEqual(profile.poc_bin, 0)
        self.assertEqual(profile.val_bin, 0)
        self.assertEqual(profile.vah_bin, 0)
        self.assertAlmostEqual(profile.val, 0.0)
        self.assertAlmostEqual(profile.vah, bin_size)

    def test_value_area_spans_internal_gap(self) -> None:
        bin_size = 0.001
        profile = build_profile(
            [0.00025, 0.00225],
            bin_size=bin_size,
            value_area_target=0.70,
            tail_bins=2,
            single_print_max_ticks=1,
            min_ticks=1,
            current_price=0.00025,
        )
        assert profile is not None
        self.assertEqual(profile.value_area_ticks, 2)
        self.assertEqual(profile.lowest_bin, 0)
        self.assertEqual(profile.highest_bin, 2)
        self.assertAlmostEqual(profile.vah, 3 * bin_size)


if __name__ == "__main__":
    unittest.main()
