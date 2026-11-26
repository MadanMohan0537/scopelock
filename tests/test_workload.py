import unittest

from scopelock.workload import (
    WorkloadScenario,
    approval_workload_budget,
    default_workload_budget,
    simulate_approval_queue,
)


class ApprovalWorkloadTests(unittest.TestCase):
    def test_default_budget_passes_base_and_blocks_surge(self):
        result = default_workload_budget()
        by_name = {row["scenario"]: row for row in result["scenarios"]}
        self.assertTrue(by_name["base"]["accepted"])
        self.assertFalse(by_name["surge"]["accepted"])
        self.assertEqual(result["recommendation"], "block")
        self.assertEqual(result["failed_scenarios"], ["surge"])

    def test_simulation_is_reproducible_and_reports_denominators(self):
        scenario = WorkloadScenario("base", 6, 6, 2, 8, 20, 10, .05)
        first = simulate_approval_queue(scenario, seed=2606)
        second = simulate_approval_queue(scenario, seed=2606)
        self.assertEqual(first, second)
        self.assertEqual(first["arrivals"], first["served"] + first["abandoned"])
        self.assertIsNotNone(first["offered_wait_p95_minutes"])

    def test_more_capacity_reduces_wait_and_promotes(self):
        constrained = WorkloadScenario("load", 12, 6, 1, 8, 20, 10, .05)
        staffed = WorkloadScenario("load", 12, 6, 4, 8, 20, 10, .05)
        before = simulate_approval_queue(constrained, seed=99)
        after = simulate_approval_queue(staffed, seed=99)
        self.assertGreater(before["offered_wait_p95_minutes"], after["offered_wait_p95_minutes"])
        self.assertTrue(after["accepted"])

    def test_sensitivity_sweep_exposes_service_time_risk(self):
        scenario = WorkloadScenario("base", 8, 5, 2, 8, 20, 10, .05)
        result = approval_workload_budget(
            [scenario], seed=10, service_time_multipliers=(.5, 2.0)
        )
        fast, slow = result["sensitivity"]
        self.assertLess(
            fast["scenarios"][0]["offered_wait_p95_minutes"],
            slow["scenarios"][0]["offered_wait_p95_minutes"],
        )

    def test_invalid_scenarios_fail_closed(self):
        invalid = WorkloadScenario("bad", 0, 5, 1, 8, 20, 10, .05)
        with self.assertRaises(ValueError):
            simulate_approval_queue(invalid, seed=1)
        valid = WorkloadScenario("same", 1, 1, 1, 1, 1, 1, 0)
        with self.assertRaises(ValueError):
            approval_workload_budget([valid, valid])
        with self.assertRaises(ValueError):
            approval_workload_budget([valid], service_time_multipliers=(0,))


if __name__ == "__main__":
    unittest.main()
