# Threat model

ScopeLock assumes an agent may hallucinate, receive prompt injection, retry calls, or have its proposed arguments changed between approval and execution. The gateway—not the prompt—is the enforcement boundary.

| Asset | Threat | Implemented control | Residual risk |
|---|---|---|---|
| Tool authority | Unknown or over-scoped tool | deny-by-default registry and per-agent scopes | host process could bypass the gateway |
| Money | Excessive or redirected transfer | limits, recipient allowlist, distinct dual approval | policy configuration can be wrong |
| Approval intent | Payload changed after review | canonical payload hash, tool version, expiry | canonicalization does not encode external state |
| Audit evidence | History edited after execution | append-only API and SHA-256 hash chain | SQLite administrator can rewrite and rehash history |
| Operations | Approval queue stalls work | automatic low-risk reads and small transfers | no SLA service in this MVP |
| External systems | Dry run causes side effects | local deterministic simulator | adapters must implement true preview semantics |
| Policy rollout | A new rule unexpectedly blocks or escalates saved calls | versioned offline migration rehearsal with declared changes | saved history does not represent novel future calls |
| Replay privacy | Historical payloads expose credentials | redacted flag, source digest, and forbidden secret-bearing keys | field-name checks do not prove semantic de-identification |
| Multi-call composition | Safe-looking calls combine into exfiltration or threshold evasion | per-agent bounded sequence rules with exact matched-action evidence | process restart, window eviction, another agent identity, or misconfigured domains can evade detection |
| Sequence reset | Reset hides prior risky actions | explicit reset API and hash-chained reset event with reason and count | no strong operator identity or approval protects reset in this MVP |

Out of scope: authentication, key custody, network isolation, durable distributed sequence state, distributed consensus, cryptographic signer identities, production policy administration, formal privacy guarantees, and security certification.

