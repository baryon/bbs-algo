# Python MVPs

[中文](README_zh.md) | English

This directory contains runnable Python MVPs for the core BBS control loops discussed in the docs.

Current demos cover three variants:

- payment authorization
- development safety guards
- cybernetics-style feedback convergence

These examples validate the engineering loop first. They are not full implementations of the paper's BBS primitive or zero-knowledge proof system.

## Files

- `bbs_payment_mvp.py`
  - Core payment authorization example
  - Includes action model, policy, signer, validator, and demo scenarios
- `run_payment_demo.py`
  - CLI runner for the payment demo
- `bbs_dev_guard_mvp.py`
  - Development safety guard example
  - Includes `db_update` and `file_rm` policies, signer, validator, and demo scenarios
- `run_dev_guard_demo.py`
  - CLI runner for the dev-guard demo
- `bbs_cybernetics_mvp.py`
  - Cybernetics-oriented feedback loop example
  - Shows how an agent revises a candidate action from structured validator feedback
- `run_cybernetics_demo.py`
  - CLI runner for the cybernetics demo

## What These MVPs Show

### Payment Authorization

The payment demo validates this loop:

`Agent -> Action -> Sign -> Validator -> Execute`

Policy:

- amount must not exceed `200 USD`
- recipient must be on the whitelist

Core components:

- `PaymentAction`
- `PaymentPolicy`
- `PolicyBoundSigner`
- `PaymentValidator`

### Dev Safety Guard

The dev-guard demo applies the same loop to high-risk development actions:

- `db_update`
- `file_rm`

It shows how dangerous operations can be constrained before execution by explicit policies and validator-side rechecks.

### Cybernetics Feedback Loop

The cybernetics demo focuses on:

`Agent -> Validator -> Feedback -> Retry`

It abstracts away from payment or dev actions and shows:

- the validator as a sensor
- structured rejection reasons as error signals
- the agent as a controller that iteratively reduces deviation

## How To Run

Run from the repository root:

```bash
python3 src/python/run_payment_demo.py
python3 src/python/run_dev_guard_demo.py
python3 src/python/run_cybernetics_demo.py
```

## Demo Scenarios

### Payment Demo

The payment demo prints 6 scenarios:

1. `valid_request`
   - valid payment is accepted
2. `signer_side_reject`
   - over-limit payment is rejected by the signer
3. `validator_reject_policy_bypass`
   - direct signing bypass still fails at the validator
4. `validator_reject_unknown_key`
   - unregistered public key is rejected
5. `validator_reject_tamper`
   - payload tampering invalidates the signature
6. `validator_reject_replay`
   - replayed nonce is rejected

### Dev-Guard Demo

The dev-guard demo prints 8 scenarios:

1. `valid_db_update`
   - safe single-row `staging` update is accepted
2. `signer_reject_db_update`
   - `production` or non-whitelisted bulk update is rejected by the signer
3. `validator_reject_db_policy_bypass`
   - bypassing signer-side checks still fails at the validator
4. `valid_file_rm`
   - file removal under `/workspace/sandbox/**` is accepted
5. `signer_reject_file_rm`
   - dangerous path deletion is rejected by the signer
6. `validator_reject_file_policy_bypass`
   - bypassing file policy still fails at the validator
7. `validator_reject_unknown_key`
   - unregistered public key is rejected
8. `validator_reject_replay`
   - replayed nonce is rejected

### Cybernetics Demo

The cybernetics demo prints 4 scenarios:

1. `converges_with_structured_feedback`
   - high-resolution feedback lets the agent converge within a bounded number of rounds
2. `fails_with_coarse_feedback`
   - coarse rejection reasons reduce convergence efficiency and the loop does not pass within the iteration limit
3. `fails_with_unreachable_target`
   - the target exceeds actuator limits, so the loop stops without converging
4. `stops_without_feedback_channel`
   - when the validator provides no actionable feedback, the loop cannot continue

## Design Boundaries

These examples are intentionally simple:

- they use `Ed25519` ordinary signatures where signing is involved
- policy enforcement is explicit logic, not zero-knowledge proof verification
- validators re-run policy checks
- no on-chain logic, consensus, or gas model is included
- `db_update` and `file_rm` cover only minimal example rules
- the cybernetics demo only models feedback convergence, not real signer or BBS proof machinery

So the right framing is:

`engineering MVPs for BBS-style control loops`

not:

`a complete BBS / PS-CMA / ZK implementation`

## Why They Are Still Useful

Even in this simplified form, the demos verify important engineering questions:

- are high-risk actions structured before execution
- does the signer reject invalid requests early
- does the validator enforce registered identity and payload binding
- does nonce-based replay protection work
- can dangerous DB and file operations be blocked deterministically
- can structured feedback drive an agent toward convergence

These are the parts worth validating before moving to a stronger BBS or ZK-backed implementation.

## Possible Extensions

- wrap validators as HTTP services
- add richer payment policies, such as daily quotas and rate limits
- extend the action model to `api_call`, `fs.delete`, and `db.query`
- replace ordinary signatures with proof-carrying signature schemes
- add finer-grained field, directory, and environment policies for dev actions
- map the cybernetics feedback protocol onto real signer and validator interfaces
