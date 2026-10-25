import unittest
from copy import deepcopy
from hashlib import sha256

from scopelock.migration import PolicyVersion, ReplayCall, rehearse_policy
from scopelock.models import ToolCall, ToolSpec
from scopelock.policy import DEFAULT_POLICY, PolicyEngine


STAMP = "2026-10-09T12:00:00+00:00"
TOOLS = {
    "ledger.read": ToolSpec("ledger.read", "1.0", "ledger.read", "read"),
    "ledger.transfer": ToolSpec(
        "ledger.transfer", "2.1", "ledger.transfer", "write"
    ),
}


def replay(call_id, tool, arguments):
    return ReplayCall(
        ToolCall(call_id, "operator", tool, arguments, STAMP),
        True,
        sha256(call_id.encode()).hexdigest(),
    )


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.old = deepcopy(DEFAULT_POLICY)
        self.new = deepcopy(DEFAULT_POLICY)
        self.new["transfer_auto_limit"] = 50.0
        self.new["allowed_recipients"] = ["vendor-42"]
        self.calls = [
            replay("control-read", "ledger.read", {"account": "operating"}),
            replay("approval-escalation", "ledger.transfer",
                   {"amount": 75, "recipient": "vendor-42"}),
            replay("new-denial", "ledger.transfer",
                   {"amount": 20, "recipient": "customer-7"}),
            replay("control-existing-denial", "ledger.transfer",
                   {"amount": 20, "recipient": "attacker"}),
        ]

    def run_rehearsal(self, expected):
        return rehearse_policy(
            PolicyVersion("v1", self.old),
            PolicyVersion("v2", self.new),
            self.calls,
            TOOLS,
            set(expected),
        )

    def test_detects_all_seeded_behavior_changes(self):
        result = self.run_rehearsal({"approval-escalation", "new-denial"})
        self.assertEqual(result["recommendation"], "promote")
        self.assertEqual(result["allow_to_deny"], ["new-denial"])
        self.assertEqual(result["approval_escalations"], ["approval-escalation"])
        self.assertEqual(result["changed_calls"], 2)

    def test_unexpected_change_blocks_promotion(self):
        result = self.run_rehearsal({"new-denial"})
        self.assertEqual(result["recommendation"], "block")
        self.assertEqual(result["unexpected_changes"], ["approval-escalation"])

    def test_missing_expected_change_blocks_promotion(self):
        result = self.run_rehearsal(
            {"approval-escalation", "new-denial", "control-read"}
        )
        self.assertEqual(result["recommendation"], "block")
        self.assertEqual(result["missing_expected_changes"], ["control-read"])

    def test_rehearsal_does_not_mutate_policy_inputs(self):
        old_before = deepcopy(self.old)
        self.run_rehearsal({"approval-escalation", "new-denial"})
        self.assertEqual(self.old, old_before)

    def test_requires_redacted_corpus_and_rejects_secret_keys(self):
        unredacted = ReplayCall(self.calls[0].call, False, self.calls[0].source_digest)
        with self.assertRaises(ValueError):
            rehearse_policy(
                PolicyVersion("v1", self.old), PolicyVersion("v2", self.new),
                [unredacted], TOOLS,
            )
        secret = replay("secret", "ledger.read", {"token": "do-not-store"})
        with self.assertRaises(ValueError):
            rehearse_policy(
                PolicyVersion("v1", self.old), PolicyVersion("v2", self.new),
                [secret], TOOLS,
            )

    def test_requires_registered_tools_and_distinct_versions(self):
        with self.assertRaises(ValueError):
            rehearse_policy(
                PolicyVersion("v1", self.old), PolicyVersion("v1", self.new),
                self.calls, TOOLS,
            )
        unknown = replay("unknown", "shell.root", {})
        with self.assertRaises(ValueError):
            rehearse_policy(
                PolicyVersion("v1", self.old), PolicyVersion("v2", self.new),
                [unknown], TOOLS,
            )

    def test_empty_policy_is_not_replaced_by_defaults(self):
        engine = PolicyEngine({})
        decision = engine.evaluate(
            self.calls[0].call, TOOLS["ledger.read"]
        )
        self.assertEqual(decision.outcome, "deny")


if __name__ == "__main__":
    unittest.main()
