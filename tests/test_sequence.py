import unittest
from datetime import datetime, timedelta, timezone

from scopelock.approvals import Approval, payload_hash
from scopelock.gateway import build_gateway
from scopelock.models import ToolCall
from scopelock.sequence import SequenceGuard


STAMP = "2026-10-09T12:00:00+00:00"


def call(call_id, agent, tool, arguments, dry=False):
    return ToolCall(call_id, agent, tool, arguments, STAMP, dry)


class SequencePolicyTests(unittest.TestCase):
    def test_read_then_external_email_is_blocked_with_exact_evidence(self):
        gateway = build_gateway()
        self.assertEqual("executed", gateway.handle(call(
            "read", "operator", "crm.read", {"customer_id": "customer-7"}
        )).outcome)
        result = gateway.handle(call(
            "send", "operator", "email.send",
            {"to": "collector@outside.test", "subject": "customer export"},
        ))
        self.assertEqual("denied", result.outcome)
        self.assertEqual("read_then_external_email", result.detail["sequence"]["rule"])
        self.assertEqual(["read", "send"], result.detail["sequence"]["matched_call_ids"])
        self.assertEqual([], gateway.env.outbox)

    def test_split_transfer_is_blocked_before_second_side_effect(self):
        gateway = build_gateway()
        first = call("t1", "operator", "ledger.transfer", {"amount": 60, "recipient": "vendor-42"})
        second = call("t2", "operator", "ledger.transfer", {"amount": 60, "recipient": "vendor-42"})
        self.assertEqual("executed", gateway.handle(first).outcome)
        result = gateway.handle(second)
        self.assertEqual("denied", result.outcome)
        self.assertEqual("split_transfer_limit", result.detail["sequence"]["rule"])
        self.assertEqual(120.0, result.detail["sequence"]["evidence"]["cumulative_amount"])
        self.assertEqual(60.0, gateway.env.ledger["vendor-42"])

    def test_benign_multistep_workflow_remains_allowed(self):
        gateway = build_gateway()
        cases = (
            call("read", "operator", "ledger.read", {"account": "operating"}),
            call("t1", "operator", "ledger.transfer", {"amount": 40, "recipient": "vendor-42"}),
            call("t2", "operator", "ledger.transfer", {"amount": 50, "recipient": "vendor-42"}),
            call("mail", "operator", "email.send", {"to": "ops@example.test", "subject": "done"}),
        )
        self.assertEqual(["executed"] * 4, [gateway.handle(item).outcome for item in cases])

    def test_histories_are_isolated_per_agent(self):
        gateway = build_gateway()
        gateway.handle(call("read", "researcher", "crm.read", {"customer_id": "customer-7"}))
        result = gateway.handle(call(
            "send", "operator", "email.send", {"to": "outside@external.test", "subject": "hello"}
        ))
        self.assertEqual("executed", result.outcome)

    def test_explicit_reset_is_audited_and_clears_history(self):
        gateway = build_gateway()
        gateway.handle(call("read", "operator", "crm.read", {"customer_id": "customer-7"}))
        self.assertEqual(1, gateway.reset_sequence("operator", STAMP, "case closed"))
        result = gateway.handle(call(
            "send", "operator", "email.send", {"to": "outside@external.test", "subject": "hello"}
        ))
        self.assertEqual("executed", result.outcome)
        self.assertEqual("sequence_reset", gateway.audit.entries()[-2]["event"])

    def test_window_eviction_is_deterministic(self):
        gateway = build_gateway(sequence_window=2)
        gateway.handle(call("read", "operator", "crm.read", {"customer_id": "customer-7"}))
        gateway.handle(call("safe1", "operator", "ledger.read", {"account": "operating"}))
        gateway.handle(call("safe2", "operator", "ledger.transfer", {"amount": 10, "recipient": "vendor-42"}))
        # The original CRM read is evicted, but the newer ledger read still makes
        # external email a matched sequence.
        blocked = gateway.handle(call(
            "send1", "operator", "email.send", {"to": "x@external.test", "subject": "x"}
        ))
        self.assertEqual(["safe1", "send1"], blocked.detail["sequence"]["matched_call_ids"])
        gateway.reset_sequence("operator", STAMP, "new task")
        gateway.handle(call("safe3", "operator", "ledger.transfer", {"amount": 10, "recipient": "vendor-42"}))
        gateway.handle(call("safe4", "operator", "ledger.transfer", {"amount": 10, "recipient": "customer-7"}))
        allowed = gateway.handle(call(
            "send2", "operator", "email.send", {"to": "x@external.test", "subject": "x"}
        ))
        self.assertEqual("executed", allowed.outcome)

    def test_dry_run_explains_block_without_mutating_history(self):
        gateway = build_gateway()
        gateway.handle(call("read", "operator", "crm.read", {"customer_id": "customer-7"}))
        result = gateway.handle(call(
            "preview", "operator", "email.send",
            {"to": "x@external.test", "subject": "x"}, True,
        ))
        self.assertEqual("dry_run", result.outcome)
        self.assertEqual("denied", result.detail["would_outcome"])
        self.assertEqual(["read"], [item.call_id for item in gateway.sequence.history("operator")])

    def test_bound_approved_transfer_is_not_treated_as_split_evasion(self):
        gateway = build_gateway()
        transfer = call("approved", "operator", "ledger.transfer", {"amount": 250, "recipient": "vendor-42"})
        approval = Approval(
            "approval", payload_hash(transfer.tool, "2.1", transfer.arguments), "finance",
            (datetime.fromisoformat(STAMP) + timedelta(minutes=5)).isoformat(),
        )
        gateway.approvals.add(approval)
        self.assertEqual("executed", gateway.handle(transfer, ["approval"]).outcome)

    def test_sequence_guard_rejects_invalid_configuration(self):
        with self.assertRaises(ValueError):
            SequenceGuard(window_size=0)
        with self.assertRaises(ValueError):
            SequenceGuard(split_transfer_limit=0)


if __name__ == "__main__":
    unittest.main()
