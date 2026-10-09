# Product backlog

Shipped features are separated from hypotheses. Every proposed addition has a concrete test and a reason it may not be worth building.

| Priority | Feature | User problem and behavior | Dependencies | Success test | Risks / tradeoffs | Status |
|---|---|---|---|---|---|---|
| P1 | Approval binding | Approved actions can change before execution. Bind canonical arguments, tool version, and expiry; require distinct approvers. | Approval store, canonical JSON | Amount, recipient, expiry, or version mutation invalidates 100% of frozen approvals; unchanged request executes | Equivalent representations need explicit normalization | Shipped |
| P2 | Policy migration rehearsal | Owners cannot see whom a new rule blocks. Replay redacted calls under old/new policies and report allow-to-deny transitions. | Versioned policies, replay corpus | Detect every seeded behavior change before promotion | History misses novel future calls; add adversarial fixtures | Planned |
| P2 | Sequence policy | Individually safe calls can form a harmful chain. Add rolling per-agent state and deny risky sequences. | Window store, sequence DSL | Block seeded read-exfiltrate and split-transfer attacks without blocking benign workflow | Stateful policy is harder to explain and recover | Planned |
| P2 | Approval workload budget | Safe controls can make the agent unusable. Forecast approval volume and wait time before rule rollout. | Arrival/service-time assumptions | Keep p95 approval wait under declared SLA in surge simulation | Results are assumption-sensitive; sweep ranges | Planned |
| P2 | Signed policy bundles | A policy edit can silently weaken controls. Sign reviewed versions and pin executions to a digest. | Key management, policy registry | Unauthorized modification is rejected; rollback remains possible | Introduces operational key custody | Planned |
| P3 | Idempotency keys | Retries can duplicate side effects. Bind operation IDs to result state. | Durable operation store, adapter contract | Timeout/retry produces exactly one transfer | External APIs may not support idempotency | Planned |
| P3 | Evidence-minimized audit | Full payloads aid review but may expose personal data. Store typed redactions plus integrity commitments. | Data classification, retention rules | Reviewers answer audit questions while seeded secrets never enter storage | Redaction may remove context needed for investigation | Planned |
| P3 | Break-glass path | Incidents need emergency action without normal latency. Add time-boxed elevated scope and mandatory review. | Strong identity, alerts | Emergency scenario succeeds and every use reaches post-review | Becomes a bypass if routinely used | Planned |
| P4 | Policy counterexample generator | Rule authors miss boundary cases. Generate deterministic candidates around thresholds and scope edges. | Policy parser, fixture generator | Finds seeded gaps with bounded false-review load | Generated cases can create false confidence | Planned |

Next slice: policy migration rehearsal. It adds decision value before expanding tool adapters and directly measures control regressions.
