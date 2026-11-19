import unittest

from engine.router import BELOW_HURDLE, NO_MODEL, breakeven_win_rate, expected_value, route

from .helpers import make_config


class RouterTests(unittest.TestCase):
    def test_expected_value_matches_the_payout_formula(self) -> None:
        self.assertAlmostEqual(expected_value(0.60, 0.80), 0.08)
        self.assertAlmostEqual(expected_value(0.50, 0.80), -0.10)

    def test_breakeven_matches_the_inverse_of_one_plus_payout(self) -> None:
        self.assertAlmostEqual(breakeven_win_rate(0.80), 1 / 1.80)

    def test_clear_edge_selects_a_call(self) -> None:
        proposal = route({60: 0.60}, make_config())

        self.assertTrue(proposal.actionable)
        self.assertEqual(proposal.direction, "call")
        self.assertEqual(proposal.horizon_seconds, 60)
        self.assertEqual(proposal.reason, "selected")

    def test_clear_negative_edge_selects_a_put(self) -> None:
        proposal = route({60: 0.20}, make_config())

        self.assertTrue(proposal.actionable)
        self.assertEqual(proposal.direction, "put")
        self.assertGreater(proposal.expected_value or 0, 0)

    def test_probability_without_edge_is_no_trade(self) -> None:
        proposal = route({60: 0.50}, make_config())

        self.assertFalse(proposal.actionable)
        self.assertEqual(proposal.direction, "no_trade")
        self.assertEqual(proposal.reason, BELOW_HURDLE)
        self.assertIsNotNone(proposal.expected_value)

    def test_empty_probabilities_are_no_trade(self) -> None:
        proposal = route({}, make_config())

        self.assertEqual(proposal.reason, NO_MODEL)
        self.assertIsNone(proposal.expected_value)

    def test_earliest_horizon_wins_when_both_clear_the_hurdle(self) -> None:
        proposal = route({60: 0.60, 90: 0.70}, make_config())

        self.assertEqual(proposal.horizon_seconds, 60)
        self.assertEqual(proposal.direction, "call")

    def test_highest_ev_tie_break_prefers_the_larger_edge(self) -> None:
        config = make_config(router={"tie_break": "highest_ev"})
        proposal = route({60: 0.60, 90: 0.70}, config)

        self.assertEqual(proposal.horizon_seconds, 90)
        self.assertAlmostEqual(proposal.expected_value or 0, 0.70 * 1.8 - 1)

    def test_hurdle_is_configurable(self) -> None:
        config = make_config(router={"min_ev": 0.50})
        proposal = route({60: 0.60}, config)

        self.assertFalse(proposal.actionable)
        self.assertEqual(proposal.reason, BELOW_HURDLE)

    def test_out_of_range_probability_is_ignored(self) -> None:
        proposal = route({60: 1.5}, make_config())

        self.assertEqual(proposal.direction, "no_trade")


if __name__ == "__main__":
    unittest.main()
