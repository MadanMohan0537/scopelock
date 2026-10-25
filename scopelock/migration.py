"""Offline policy migration rehearsal over a redacted call corpus."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from .models import ToolCall, ToolSpec
from .policy import PolicyEngine


FORBIDDEN_ARGUMENT_KEYS = {
    "password", "secret", "token", "api_key", "access_token", "ssn"
}


@dataclass(frozen=True)
class PolicyVersion:
    version: str
    policy: dict[str, Any]

    @property
    def digest(self) -> str:
        body = json.dumps(self.policy, sort_keys=True, separators=(",", ":"))
        return sha256(body.encode()).hexdigest()


@dataclass(frozen=True)
class ReplayCall:
    call: ToolCall
    redacted: bool
    source_digest: str


def _validate_replay(item: ReplayCall) -> None:
    if not item.redacted:
        raise ValueError(f"{item.call.call_id}: replay input must be redacted")
    if len(item.source_digest) != 64 or any(
        char not in "0123456789abcdef" for char in item.source_digest
    ):
        raise ValueError(f"{item.call.call_id}: source_digest must be sha256 hex")
    present = {str(key).lower() for key in item.call.arguments}
    forbidden = sorted(present & FORBIDDEN_ARGUMENT_KEYS)
    if forbidden:
        raise ValueError(
            f"{item.call.call_id}: forbidden argument keys: {','.join(forbidden)}"
        )


def rehearse_policy(
    old: PolicyVersion,
    new: PolicyVersion,
    calls: list[ReplayCall],
    tools: dict[str, ToolSpec],
    expected_changed_call_ids: set[str] | None = None,
) -> dict:
    """Compare decisions without executing tools or writing to the audit log."""
    if old.version == new.version:
        raise ValueError("old and new policy versions must differ")
    ids = [item.call.call_id for item in calls]
    if len(ids) != len(set(ids)):
        raise ValueError("replay call ids must be unique")
    expected = set(expected_changed_call_ids or set())
    unknown_expected = expected - set(ids)
    if unknown_expected:
        raise ValueError("expected change ids must exist in the replay corpus")

    old_engine, new_engine = PolicyEngine(old.policy), PolicyEngine(new.policy)
    transitions = []
    for item in calls:
        _validate_replay(item)
        spec = tools.get(item.call.tool)
        if spec is None:
            raise ValueError(f"{item.call.call_id}: tool is not registered")
        before = old_engine.evaluate(item.call, spec)
        after = new_engine.evaluate(item.call, spec)
        changed = before.outcome != after.outcome or before.reasons != after.reasons
        transitions.append({
            "call_id": item.call.call_id,
            "tool": item.call.tool,
            "old_outcome": before.outcome,
            "new_outcome": after.outcome,
            "old_reasons": list(before.reasons),
            "new_reasons": list(after.reasons),
            "changed": changed,
            "expected_change": item.call.call_id in expected,
            "source_digest": item.source_digest,
        })

    observed = {row["call_id"] for row in transitions if row["changed"]}
    unexpected = sorted(observed - expected)
    missing = sorted(expected - observed)
    matrix: dict[str, int] = {}
    for row in transitions:
        key = f"{row['old_outcome']}->{row['new_outcome']}"
        matrix[key] = matrix.get(key, 0) + 1
    return {
        "old_policy": {"version": old.version, "digest": old.digest},
        "new_policy": {"version": new.version, "digest": new.digest},
        "corpus_size": len(calls),
        "changed_calls": len(observed),
        "transition_matrix": matrix,
        "allow_to_deny": [
            row["call_id"] for row in transitions
            if row["old_outcome"] == "allow" and row["new_outcome"] == "deny"
        ],
        "approval_escalations": [
            row["call_id"] for row in transitions
            if row["old_outcome"] == "allow"
            and row["new_outcome"] == "approval_required"
        ],
        "unexpected_changes": unexpected,
        "missing_expected_changes": missing,
        "recommendation": "promote" if not unexpected and not missing else "block",
        "transitions": transitions,
    }
