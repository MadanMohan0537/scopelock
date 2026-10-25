# Product backlog

Shipped features are separated from hypotheses. Every proposed addition has a concrete test and a reason it may not be worth building.

| Priority | Feature | User problem and behavior | Dependencies | Success test | Risks / tradeoffs | Status |
|---|---|---|---|---|---|---|
| P1 | Approval binding | Approved actions can change before execution. Bind canonical arguments, tool version, and expiry; require distinct approvers. | Approval store, canonical JSON | Amount, recipient, expiry, or version mutation invalidates 100% of frozen approvals; unchanged request executes | Equivalent representations need explicit normalization | Shipped |
| P2 | Policy migration rehearsal | Owners cannot see whom a new rule blocks. Replay redacted calls under old/new policies, compare reasons, and gate promotion against declared changes. | Versioned policies, redacted replay corpus, tool registry | Frozen corpus detects one allow-to-deny and one approval escalation; missing or unexpected changes block promotion | History misses novel future calls; redaction assertion is not a privacy proof | Shipped |
| P2 | Sequence policy | Individually safe calls can form a harmful chain. Add rolling per-agent state and deny risky sequences. | Window store, sequence DSL | Block seeded read-exfiltrate and split-transfer attacks without blocking benign workflow | Stateful policy is harder to explain and recover | Planned |
| P2 | Approval workload budget | Safe controls can make the agent unusable. Forecast approval volume and wait time before rule rollout. | Arrival/service-time assumptions | Keep p95 approval wait under declared SLA in surge simulation | Results are assumption-sensitive; sweep ranges | Planned |
| P2 | Signed policy bundles | A policy edit can silently weaken controls. Sign reviewed versions and pin executions to a digest. | Key management, policy registry | Unauthorized modification is rejected; rollback remains possible | Introduces operational key custody | Planned |
| P3 | Idempotency keys | Retries can duplicate side effects. Bind operation IDs to result state. | Durable operation store, adapter contract | Timeout/retry produces exactly one transfer | External APIs may not support idempotency | Planned |
| P3 | Evidence-minimized audit | Full payloads aid review but may expose personal data. Store typed redactions plus integrity commitments. | Data classification, retention rules | Reviewers answer audit questions while seeded secrets never enter storage | Redaction may remove context needed for investigation | Planned |
| P3 | Break-glass path | Incidents need emergency action without normal latency. Add time-boxed elevated scope and mandatory review. | Strong identity, alerts | Emergency scenario succeeds and every use reaches post-review | Becomes a bypass if routinely used | Planned |
| P4 | Policy counterexample generator | Rule authors miss boundary cases. Generate deterministic candidates around thresholds and scope edges. | Policy parser, fixture generator | Finds seeded gaps with bounded false-review load | Generated cases can create false confidence | Planned |
| P3 | Corpus coverage frontier | A clean rehearsal may cover only trivial policy branches. Report exercised scopes, recipients, time windows, and threshold boundaries. | Policy branch inventory, corpus tags | Promotion blocks when a declared critical branch has no replay example | Coverage can reward synthetic quantity instead of realism | Planned |
| P3 | Reason-contract compatibility | Integrations can break when a decision stays deny but its reason changes. Version reason codes and flag consumer-visible changes separately. | Reason schema, consumer registry | Seeded reason-only change reaches every subscribed consumer test | Stable codes can slow useful taxonomy changes | Planned |

Next slice: sequence-aware policy. Track a bounded per-agent action window and
block seeded read-then-exfiltrate and split-transfer attacks while preserving a
benign multi-step fixture. Publish the exact matched sequence and state reset
rules so denials remain explainable.

