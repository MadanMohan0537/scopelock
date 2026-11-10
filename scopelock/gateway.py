from __future__ import annotations

from .approvals import ApprovalStore
from .audit import AuditLog
from .models import ExecutionResult, ToolCall, ToolSpec
from .policy import PolicyEngine
from .tools import ToyEnvironment
from .sequence import SequenceGuard


class Gateway:
    def __init__(self, policy: PolicyEngine, approvals: ApprovalStore, audit: AuditLog, env: ToyEnvironment, sequence: SequenceGuard):
        self.policy, self.approvals, self.audit, self.env = policy, approvals, audit, env
        self.sequence = sequence
        self.tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self.tools[spec.name] = spec

    def handle(self, call: ToolCall, approval_ids: list[str] | None = None) -> ExecutionResult:
        spec = self.tools.get(call.tool)
        if not spec:
            self.audit.append(call.requested_at, "denied", {"call_id": call.call_id, "reason": "unknown_tool"})
            return ExecutionResult(call.call_id, "denied", {"reasons": ["unknown_tool"]})
        decision = self.policy.evaluate(call, spec)
        detail = {"reasons": list(decision.reasons), "approvals_required": decision.approvals_required}
        if decision.outcome == "deny":
            self.audit.append(call.requested_at, "denied", {"call": call.__dict__, **detail})
            return ExecutionResult(call.call_id, "denied", detail)
        if decision.outcome == "approval_required":
            approvers = self.approvals.valid_approvers(
                approval_ids or [], tool=call.tool, tool_version=spec.version,
                arguments=call.arguments, now=call.requested_at,
            )
            detail["valid_approvers"] = sorted(approvers)
            if len(approvers) < decision.approvals_required:
                self.audit.append(call.requested_at, "approval_required", {"call": call.__dict__, **detail})
                return ExecutionResult(call.call_id, "approval_required", detail)
        sequence = self.sequence.evaluate(
            call, direct_policy_allow=decision.outcome == "allow"
        )
        detail["sequence"] = sequence.to_dict()
        if call.dry_run:
            self.audit.append(call.requested_at, "dry_run", {"call": call.__dict__, **detail})
            return ExecutionResult(call.call_id, "dry_run", {
                **detail,
                "would_execute": call.tool if sequence.allowed else None,
                "would_outcome": "executed" if sequence.allowed else "denied",
            })
        if not sequence.allowed:
            detail["reasons"] = [*detail["reasons"], "sequence_policy"]
            self.audit.append(call.requested_at, "denied", {"call": call.__dict__, **detail})
            return ExecutionResult(call.call_id, "denied", detail)
        result = self.env.execute(call.tool, call.arguments)
        self.sequence.record(call)
        self.audit.append(call.requested_at, "executed", {"call": call.__dict__, "result": result, **detail})
        return ExecutionResult(call.call_id, "executed", result)

    def reset_sequence(self, agent_id: str, at: str, reason: str) -> int:
        if not reason.strip():
            raise ValueError("sequence reset requires a reason")
        removed = self.sequence.reset(agent_id)
        self.audit.append(at, "sequence_reset", {
            "agent_id": agent_id, "reason": reason, "removed_actions": removed,
        })
        return removed


def build_gateway(audit_path: str = ":memory:", *, sequence_window: int = 5) -> Gateway:
    gateway = Gateway(
        PolicyEngine(), ApprovalStore(), AuditLog(audit_path), ToyEnvironment(),
        SequenceGuard(sequence_window),
    )
    for spec in (
        ToolSpec("ledger.read", "1.0", "ledger.read", "read"),
        ToolSpec("crm.read", "1.0", "crm.read", "read"),
        ToolSpec("email.send", "1.0", "email.send", "write"),
        ToolSpec("ledger.transfer", "2.1", "ledger.transfer", "write"),
    ):
        gateway.register(spec)
    return gateway

