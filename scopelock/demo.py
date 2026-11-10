from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .approvals import Approval, payload_hash
from .gateway import build_gateway
from .models import ToolCall
from .models import ToolSpec
from .migration import PolicyVersion, ReplayCall, rehearse_policy
from .policy import DEFAULT_POLICY
from copy import deepcopy
from hashlib import sha256


def run_sequence_experiment() -> dict:
    gateway = build_gateway()
    timestamp = "2026-10-09T12:00:00+00:00"
    read = ToolCall(
        "seq-read", "operator", "crm.read",
        {"customer_id": "customer-7"}, timestamp,
    )
    exfiltrate = ToolCall(
        "seq-exfil", "operator", "email.send",
        {"to": "collector@outside.test", "subject": "customer export"},
        timestamp,
    )
    first_transfer = ToolCall(
        "seq-transfer-1", "operator", "ledger.transfer",
        {"amount": 60, "recipient": "vendor-42"}, timestamp,
    )
    second_transfer = ToolCall(
        "seq-transfer-2", "operator", "ledger.transfer",
        {"amount": 60, "recipient": "vendor-42"}, timestamp,
    )
    gateway.handle(read)
    exfiltration_result = gateway.handle(exfiltrate)
    gateway.handle(first_transfer)
    split_result = gateway.handle(second_transfer)
    reset_actions = gateway.reset_sequence("operator", timestamp, "new task boundary")
    benign = [
        gateway.handle(ToolCall(
            "benign-1", "operator", "ledger.transfer",
            {"amount": 40, "recipient": "vendor-42"}, timestamp,
        )),
        gateway.handle(ToolCall(
            "benign-2", "operator", "ledger.transfer",
            {"amount": 50, "recipient": "vendor-42"}, timestamp,
        )),
        gateway.handle(ToolCall(
            "benign-email", "operator", "email.send",
            {"to": "ops@example.test", "subject": "complete"}, timestamp,
        )),
    ]
    return {
        "read_then_external_email": exfiltration_result.detail["sequence"],
        "split_transfer": split_result.detail["sequence"],
        "reset_actions": reset_actions,
        "benign_outcomes": [item.outcome for item in benign],
        "blocked_attacks": sum(
            item.outcome == "denied" for item in (exfiltration_result, split_result)
        ),
        "benign_executed": sum(item.outcome == "executed" for item in benign),
        "audit_chain_valid": gateway.audit.verify(),
    }


def run_demo(audit_path: str = "scopelock.db") -> dict:
    gateway = build_gateway(audit_path)
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    timestamp = now.isoformat()
    cases = [
        ToolCall("read-1", "researcher", "ledger.read", {"account": "operating"}, timestamp),
        ToolCall("blocked-1", "researcher", "ledger.transfer", {"amount": 20, "recipient": "vendor-42"}, timestamp),
        ToolCall("dry-1", "operator", "email.send", {"to": "ops@example.test", "subject": "Status"}, timestamp, True),
        ToolCall("auto-1", "operator", "ledger.transfer", {"amount": 75, "recipient": "vendor-42"}, timestamp),
        ToolCall("approve-1", "operator", "ledger.transfer", {"amount": 250, "recipient": "vendor-42"}, timestamp),
    ]
    results = [gateway.handle(call) for call in cases]
    requested = cases[-1]
    approval = Approval(
        "approval-1", payload_hash(requested.tool, "2.1", requested.arguments), "finance-lead",
        (now + timedelta(minutes=15)).isoformat(),
    )
    gateway.approvals.add(approval)
    results.append(gateway.handle(requested, [approval.approval_id]))
    tampered = ToolCall("tamper-1", "operator", "ledger.transfer", {"amount": 251, "recipient": "vendor-42"}, timestamp)
    results.append(gateway.handle(tampered, [approval.approval_id]))
    old_policy = deepcopy(DEFAULT_POLICY)
    new_policy = deepcopy(DEFAULT_POLICY)
    new_policy["transfer_auto_limit"] = 50.0
    new_policy["allowed_recipients"] = ["vendor-42"]
    replay_calls = [
        ReplayCall(cases[0], True, sha256(b"read-1").hexdigest()),
        ReplayCall(cases[3], True, sha256(b"auto-1").hexdigest()),
        ReplayCall(
            ToolCall("removed-recipient", "operator", "ledger.transfer",
                     {"amount": 20, "recipient": "customer-7"}, timestamp),
            True, sha256(b"removed-recipient").hexdigest(),
        ),
    ]
    specs = {
        "ledger.read": ToolSpec("ledger.read", "1.0", "ledger.read", "read"),
        "ledger.transfer": ToolSpec("ledger.transfer", "2.1", "ledger.transfer", "write"),
    }
    migration = rehearse_policy(
        PolicyVersion("2026-10-09", old_policy),
        PolicyVersion("2026-10-10", new_policy),
        replay_calls,
        specs,
        {"auto-1", "removed-recipient"},
    )
    return {
        "results": [result.__dict__ for result in results],
        "environment": gateway.env.snapshot(),
        "audit_entries": len(gateway.audit.entries()),
        "audit_chain_valid": gateway.audit.verify(),
        "binding_experiment": {"original_executed": results[-2].outcome == "executed", "mutated_rejected": results[-1].outcome == "approval_required"},
        "migration_rehearsal": migration,
        "sequence_experiment": run_sequence_experiment(),
    }

