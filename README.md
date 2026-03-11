# BBS-Algo

**Behavior-Bounded Signatures for AI Agent Safety**

[中文](README_zh.md) | [日本語](README_ja.md) | English

---

BBS-Algo is a proof-of-concept implementation of **Behavior-Bounded Signatures (BBS)** — a cryptographic approach to constraining AI agent actions. Instead of relying on software-layer guardrails that can be bypassed by prompt injection, code bugs, or supply-chain attacks, BBS embeds policy constraints into the signature mechanism itself, making policy violations **mathematically impossible** rather than merely "checked by code."

## The Problem

Traditional AI agent authorization separates identity verification from behavioral validation:

```
Private Key + Ordinary Signature  →  "Who authorized this?"
Software Layer + Policy Checks    →  "Should they have authorized this?"
```

If an agent holds a valid key, its signatures are structurally valid regardless of whether the action violates policies. The policies live in soft layers — middleware, guardrails, prompt instructions — all of which can be bypassed.

BBS closes this gap: **if the action violates the policy, a valid signature cannot be produced. Period.**

## How It Works

```
Agent → Action → Policy-Bound Signer → Policy satisfied?
                                        ├─ Yes → Valid signature → Validator → Execute
                                        └─ No  → Mathematically impossible to sign → Rejected
```

Key properties:

- **Action Binding** — Signatures cover the entire canonicalized action; tampering any field invalidates the signature
- **Policy Fingerprint** — Cryptographic hash ensures signer and validator use the same policy version
- **Replay Protection** — One-time nonce per operation
- **Closed Execution Path** — High-risk executors accept only validated signed requests; no backdoors

## Repository Structure

```
.
├── paper/
│   ├── bbs.pdf                              # Original BBS paper
│   └── behavior-constrained-agent-systems-paper.pdf
├── docs/
│   ├── bbs-paper-explained.md               # Paper walkthrough
│   ├── bbs-application-memo.md              # Engineering design memo
│   ├── bbs-engineering-implementation.md    # Implementation guide
│   ├── behavior-constrained-agent-systems-paper.md
│   ├── ai-agent-safety-crisis-and-bbs-solution.md  # Industry context (Chinese)
│   └── ai-agent-safety-crisis-and-bbs-solution-en.md  # Industry context (English)
└── src/
    └── python/
        ├── bbs_payment_mvp.py               # Payment authorization MVP
        ├── bbs_dev_guard_mvp.py             # Dev safety guard MVP
        ├── bbs_cybernetics_mvp.py           # Control-theory feedback loop MVP
        ├── run_payment_demo.py              # Payment demo runner
        ├── run_dev_guard_demo.py            # Dev guard demo runner
        └── run_cybernetics_demo.py          # Cybernetics demo runner
```

## Quick Start

```bash
# Payment authorization demo
python3 src/python/run_payment_demo.py

# Dev safety guard demo
python3 src/python/run_dev_guard_demo.py

# Control-theory feedback loop demo
python3 src/python/run_cybernetics_demo.py
```

## MVP Coverage

### Payment Authorization

Policy: max 200 USD per transaction, whitelisted recipients only.

| Scenario | Result |
|----------|--------|
| Valid payment (168.50 USD → vendor_123) | ✅ Accepted |
| Over-limit payment (243 USD) | ❌ Signer rejects |
| Policy bypass (attacker signs directly) | ❌ Validator rejects policy mismatch |
| Unknown key | ❌ Validator rejects unregistered key |
| Payload tampering (change recipient after signing) | ❌ Signature verification fails |
| Replay attack (reuse nonce) | ❌ Validator blocks duplicate nonce |

### Dev Safety Guard

**DB Updates** — allowed only on staging, whitelisted tables/fields, single-row:

| Scenario | Result |
|----------|--------|
| staging / feature_flags / enabled / 1 row | ✅ Accepted |
| production / users / role / bulk update | ❌ Rejected |

**File Removal** — allowed only in sandbox/tmp paths:

| Scenario | Result |
|----------|--------|
| /workspace/sandbox/\*\* | ✅ Accepted |
| /etc/passwd | ❌ Rejected |

### Control-Theory Feedback Loop

Demonstrates how the BBS loop functions as a negative feedback control system. The agent iterates toward multi-dimensional acceptance criteria (quality, cost, latency, risk) guided by validator feedback.

| Scenario | Feedback Mode | Result |
|----------|---------------|--------|
| Rich feedback + reachable target | Exact deviations per dimension | ✅ Converges in 3–4 rounds |
| Coarse feedback + same target | Violation reasons only, no values | ❌ Fails to converge within budget |
| Rich feedback + unreachable target | Exact deviations | ❌ Agent hits actuator limits, stops |
| No feedback channel | Nothing returned | ❌ Agent cannot correct, stops immediately |

## Papers & Documentation

| Document | Description |
|----------|-------------|
| [paper/bbs.pdf](paper/bbs.pdf) | Original BBS paper — formal definitions of PS-CMA security model and behavior-bounded signature schemes. Zenodo: https://zenodo.org/records/18811273. DOI: `10.5281/zenodo.18811273` |
| [paper/behavior-constrained-agent-systems-paper.pdf](paper/behavior-constrained-agent-systems-paper.pdf) | Extended paper on behavior-constrained agent systems. Zenodo: https://zenodo.org/records/18952739. DOI: `10.5281/zenodo.18952739` |
| [docs/bbs-paper-explained.md](docs/bbs-paper-explained.md) | Accessible walkthrough of the paper's core concepts |
| [docs/bbs-application-memo.md](docs/bbs-application-memo.md) | Engineering design memo — why BBS is implemented as a "hard boundary controller" and practical deployment considerations |
| [docs/bbs-engineering-implementation.md](docs/bbs-engineering-implementation.md) | Implementation guide covering architecture layers, action modeling, and production roadmap |
| [docs/behavior-constrained-agent-systems-paper.md](docs/behavior-constrained-agent-systems-paper.md) | Full paper content in Markdown format |
| [docs/ai-agent-safety-crisis-and-bbs-solution-en.md](docs/ai-agent-safety-crisis-and-bbs-solution-en.md) | Industry context: real AI agent safety incidents and how BBS addresses them |
| [docs/ai-agent-safety-crisis-and-bbs-solution.md](docs/ai-agent-safety-crisis-and-bbs-solution.md) | Same article in Chinese (中文版) |

## Scope

This repository is an **engineering proof-of-concept**. It intentionally uses Ed25519 signatures instead of full zero-knowledge proofs to keep the control flow clear and auditable. The current MVPs validate that the `Agent → Signer → Validator → Executor` loop works end-to-end with policy binding, action binding, replay protection, structured rejection feedback, and control-theoretic convergence driven by feedback precision.

Not included: ZK proof circuits, on-chain verification, consensus protocols, production key management, or network service wrappers.

## License

MIT
