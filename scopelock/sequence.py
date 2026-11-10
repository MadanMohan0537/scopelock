"""Explainable stateful policy over bounded per-agent action histories."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from .models import ToolCall


@dataclass(frozen=True)
class ActionRecord:
    call_id: str
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class SequenceDecision:
    allowed: bool
    rule: str | None = None
    matched_call_ids: tuple[str, ...] = ()
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "rule": self.rule,
            "matched_call_ids": list(self.matched_call_ids),
            "evidence": self.evidence or {},
        }


class SequenceGuard:
    """Keep only the last N executed actions for each agent."""

    def __init__(
        self,
        window_size: int = 5,
        split_transfer_limit: float = 100.0,
        internal_email_domains: tuple[str, ...] = ("example.test",),
    ) -> None:
        if window_size < 1:
            raise ValueError("window_size must be positive")
        if split_transfer_limit <= 0:
            raise ValueError("split_transfer_limit must be positive")
        self.window_size = window_size
        self.split_transfer_limit = float(split_transfer_limit)
        self.internal_email_domains = tuple(domain.lower() for domain in internal_email_domains)
        self._history: dict[str, deque[ActionRecord]] = {}

    def history(self, agent_id: str) -> tuple[ActionRecord, ...]:
        return tuple(self._history.get(agent_id, ()))

    def record(self, call: ToolCall) -> None:
        history = self._history.setdefault(
            call.agent_id, deque(maxlen=self.window_size)
        )
        history.append(ActionRecord(call.call_id, call.tool, dict(call.arguments)))

    def reset(self, agent_id: str) -> int:
        removed = len(self._history.get(agent_id, ()))
        self._history.pop(agent_id, None)
        return removed

    def evaluate(self, call: ToolCall, *, direct_policy_allow: bool) -> SequenceDecision:
        history = self.history(call.agent_id)

        if call.tool == "email.send":
            recipient = str(call.arguments.get("to", ""))
            domain = recipient.rsplit("@", 1)[-1].lower() if "@" in recipient else ""
            is_external = not domain or domain not in self.internal_email_domains
            reads = tuple(
                item.call_id for item in history
                if item.tool in {"ledger.read", "crm.read"}
            )
            if is_external and reads:
                return SequenceDecision(
                    False,
                    "read_then_external_email",
                    (*reads, call.call_id),
                    {
                        "recipient_domain": domain or "invalid",
                        "internal_domains": list(self.internal_email_domains),
                        "window_size": self.window_size,
                    },
                )

        # An explicitly approved transfer is bound to its full amount and is not
        # treated as an attempt to evade the automatic-transfer threshold.
        if call.tool == "ledger.transfer" and direct_policy_allow:
            try:
                amount = float(call.arguments["amount"])
                recipient = str(call.arguments["recipient"])
            except (KeyError, TypeError, ValueError):
                return SequenceDecision(True)
            prior = []
            total = amount
            for item in history:
                if item.tool != "ledger.transfer":
                    continue
                if str(item.arguments.get("recipient")) != recipient:
                    continue
                try:
                    prior_amount = float(item.arguments["amount"])
                except (KeyError, TypeError, ValueError):
                    continue
                total += prior_amount
                prior.append(item.call_id)
            if prior and total > self.split_transfer_limit:
                return SequenceDecision(
                    False,
                    "split_transfer_limit",
                    (*prior, call.call_id),
                    {
                        "recipient": recipient,
                        "cumulative_amount": round(total, 6),
                        "limit": self.split_transfer_limit,
                        "window_size": self.window_size,
                    },
                )

        return SequenceDecision(True)
