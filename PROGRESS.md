# AI PM Project Lab progress

| Date | Repository | Increment | Evidence | Next repository |
|---|---|---|---|---|
| 2026-10-25 | ScopeLock | Versioned policy-migration rehearsal with transition and promotion gates | 23 tests; one denial and one escalation detected; mismatched declarations block | RiskCouncil |
| 2026-11-10 | ScopeLock | Bounded sequence policy with read-exfiltration and split-transfer controls | 32 tests; 2/2 seeded attacks blocked; 3/3 benign actions executed; resets audited | RiskCouncil |
| 2026-11-26 | ScopeLock | Approval-capacity gate with base/surge queues, SLA and abandonment budgets, and service-time sensitivity | 37 tests; base p95 0.25 min passes; surge p95 11.10 min breaches 10-minute SLA and blocks | RiskCouncil |

## Next ScopeLock increment

Implement signed, digest-pinned policy bundles with tamper rejection and a
controlled rollback experiment.
