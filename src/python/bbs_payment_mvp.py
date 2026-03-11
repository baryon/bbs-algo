"""Minimal payment-oriented BBS MVP.

This module intentionally models the control flow described in the design memo:

Agent -> Action -> Sign -> Validator -> Execute

It is not a full implementation of the paper's BBS primitive. In particular:

- it uses Ed25519 signatures from `cryptography`
- policy checks are explicit validator logic, not zero-knowledge proofs
- validator rechecks the policy instead of verifying a ZK statement

The goal is a runnable MVP for the payment example, not a production-grade
cryptographic construction.
"""

from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class PaymentAction:
    agent_id: str
    amount_cents: int
    currency: str
    recipient: str
    invoice_id: str
    epoch: int
    nonce: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "recipient": self.recipient,
            "invoice_id": self.invoice_id,
            "epoch": self.epoch,
            "nonce": self.nonce,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PaymentPolicy:
    policy_id: str
    max_amount_cents: int
    currency: str
    recipient_whitelist: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "max_amount_cents": self.max_amount_cents,
            "currency": self.currency,
            "recipient_whitelist": list(self.recipient_whitelist),
        }

    def fingerprint(self) -> str:
        return sha256_hex(canonical_json(self.to_dict()))

    def evaluate(self, action: PaymentAction) -> list[str]:
        reasons: list[str] = []
        if action.amount_cents <= 0:
            reasons.append("amount_must_be_positive")
        if action.amount_cents > self.max_amount_cents:
            reasons.append("amount_exceeds_limit")
        if action.currency != self.currency:
            reasons.append("currency_not_allowed")
        if action.recipient not in self.recipient_whitelist:
            reasons.append("recipient_not_whitelisted")
        return reasons


@dataclass(frozen=True)
class SignedPaymentRequest:
    agent_id: str
    public_key_pem: str
    policy_fingerprint: str
    action: PaymentAction
    signature_b64: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "public_key_pem": self.public_key_pem,
            "policy_fingerprint": self.policy_fingerprint,
            "action": self.action.to_dict(),
            "signature_b64": self.signature_b64,
        }


@dataclass(frozen=True)
class SigningResult:
    ok: bool
    stage: str
    reasons: tuple[str, ...] = ()
    request: SignedPaymentRequest | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "stage": self.stage,
            "reasons": list(self.reasons),
            "request": None if self.request is None else self.request.to_dict(),
        }


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    stage: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "stage": self.stage,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class RegisteredAgent:
    public_key_pem: str
    policy: PaymentPolicy


def generate_keypair() -> tuple[Ed25519PrivateKey, str]:
    private_key = Ed25519PrivateKey.generate()
    public_key_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    return private_key, public_key_pem


def build_signing_message(
    action: PaymentAction,
    policy_fingerprint: str,
) -> bytes:
    payload = {
        "action": action.to_dict(),
        "policy_fingerprint": policy_fingerprint,
    }
    return canonical_json(payload)


class PolicyBoundSigner:
    def __init__(
        self,
        agent_id: str,
        private_key: Ed25519PrivateKey,
        public_key_pem: str,
        policy: PaymentPolicy,
    ) -> None:
        self.agent_id = agent_id
        self.private_key = private_key
        self.public_key_pem = public_key_pem
        self.policy = policy

    def sign(self, action: PaymentAction) -> SigningResult:
        reasons: list[str] = []
        if action.agent_id != self.agent_id:
            reasons.append("agent_id_mismatch")
        reasons.extend(self.policy.evaluate(action))
        if reasons:
            return SigningResult(
                ok=False,
                stage="signer",
                reasons=tuple(reasons),
                request=None,
            )

        policy_fingerprint = self.policy.fingerprint()
        message = build_signing_message(action, policy_fingerprint)
        signature = self.private_key.sign(message)
        request = SignedPaymentRequest(
            agent_id=self.agent_id,
            public_key_pem=self.public_key_pem,
            policy_fingerprint=policy_fingerprint,
            action=action,
            signature_b64=b64encode(signature).decode("ascii"),
        )
        return SigningResult(ok=True, stage="signer", request=request)


class PaymentValidator:
    def __init__(self, registry: dict[str, RegisteredAgent]) -> None:
        self.registry = registry
        self._used_nonces: set[tuple[str, str]] = set()

    def validate(self, request: SignedPaymentRequest) -> ValidationResult:
        registered = self.registry.get(request.agent_id)
        if registered is None:
            return ValidationResult(
                accepted=False,
                stage="validator",
                reasons=("unknown_agent",),
            )

        reasons: list[str] = []
        if request.action.agent_id != request.agent_id:
            reasons.append("request_agent_id_mismatch")
        if request.public_key_pem != registered.public_key_pem:
            reasons.append("public_key_not_registered")
        if request.policy_fingerprint != registered.policy.fingerprint():
            reasons.append("policy_fingerprint_mismatch")

        if reasons:
            return ValidationResult(
                accepted=False,
                stage="validator",
                reasons=tuple(reasons),
            )

        message = build_signing_message(request.action, request.policy_fingerprint)
        public_key = serialization.load_pem_public_key(
            request.public_key_pem.encode("ascii")
        )
        assert isinstance(public_key, Ed25519PublicKey)

        try:
            public_key.verify(b64decode(request.signature_b64), message)
        except InvalidSignature:
            return ValidationResult(
                accepted=False,
                stage="validator",
                reasons=("invalid_signature",),
            )

        policy_reasons = registered.policy.evaluate(request.action)
        if policy_reasons:
            return ValidationResult(
                accepted=False,
                stage="validator",
                reasons=tuple(policy_reasons),
            )

        nonce_key = (request.agent_id, request.action.nonce)
        if nonce_key in self._used_nonces:
            return ValidationResult(
                accepted=False,
                stage="validator",
                reasons=("replayed_nonce",),
            )

        self._used_nonces.add(nonce_key)
        return ValidationResult(accepted=True, stage="validator")


def sign_without_policy_check(
    private_key: Ed25519PrivateKey,
    public_key_pem: str,
    agent_id: str,
    policy_fingerprint: str,
    action: PaymentAction,
) -> SignedPaymentRequest:
    """Helper used in demos to simulate a compromised or bypassing agent."""
    message = build_signing_message(action, policy_fingerprint)
    signature = private_key.sign(message)
    return SignedPaymentRequest(
        agent_id=agent_id,
        public_key_pem=public_key_pem,
        policy_fingerprint=policy_fingerprint,
        action=action,
        signature_b64=b64encode(signature).decode("ascii"),
    )


def pretty(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


def demo_scenarios() -> list[tuple[str, dict[str, Any]]]:
    policy = PaymentPolicy(
        policy_id="pay-200usd-whitelist-v1",
        max_amount_cents=20_000,
        currency="USD",
        recipient_whitelist=("vendor_123", "vendor_456"),
    )

    trusted_private_key, trusted_public_key_pem = generate_keypair()
    rogue_private_key, rogue_public_key_pem = generate_keypair()

    signer = PolicyBoundSigner(
        agent_id="agent_payment_bot",
        private_key=trusted_private_key,
        public_key_pem=trusted_public_key_pem,
        policy=policy,
    )

    validator = PaymentValidator(
        registry={
            "agent_payment_bot": RegisteredAgent(
                public_key_pem=trusted_public_key_pem,
                policy=policy,
            )
        }
    )

    valid_action = PaymentAction(
        agent_id="agent_payment_bot",
        amount_cents=16_850,
        currency="USD",
        recipient="vendor_123",
        invoice_id="inv_001",
        epoch=202603111200,
        nonce="n-001",
        reason="approved supplier payout",
    )

    over_limit_action = PaymentAction(
        agent_id="agent_payment_bot",
        amount_cents=24_300,
        currency="USD",
        recipient="vendor_123",
        invoice_id="inv_002",
        epoch=202603111205,
        nonce="n-002",
        reason="attempted over-limit payout",
    )

    signer_valid = signer.sign(valid_action)
    assert signer_valid.request is not None
    valid_result = validator.validate(signer_valid.request)

    signer_reject = signer.sign(over_limit_action)

    bypass_request = sign_without_policy_check(
        private_key=trusted_private_key,
        public_key_pem=trusted_public_key_pem,
        agent_id="agent_payment_bot",
        policy_fingerprint=policy.fingerprint(),
        action=over_limit_action,
    )
    bypass_result = validator.validate(bypass_request)

    rogue_request = sign_without_policy_check(
        private_key=rogue_private_key,
        public_key_pem=rogue_public_key_pem,
        agent_id="agent_payment_bot",
        policy_fingerprint=policy.fingerprint(),
        action=valid_action,
    )
    rogue_result = validator.validate(rogue_request)

    tampered_payload = SignedPaymentRequest(
        agent_id=signer_valid.request.agent_id,
        public_key_pem=signer_valid.request.public_key_pem,
        policy_fingerprint=signer_valid.request.policy_fingerprint,
        action=PaymentAction(
            agent_id="agent_payment_bot",
            amount_cents=16_850,
            currency="USD",
            recipient="vendor_456",
            invoice_id="inv_001",
            epoch=202603111200,
            nonce="n-003",
            reason="payload tampered after signing",
        ),
        signature_b64=signer_valid.request.signature_b64,
    )
    tampered_result = validator.validate(tampered_payload)

    replay_result = validator.validate(signer_valid.request)

    return [
        ("valid_request", valid_result.to_dict()),
        ("signer_side_reject", signer_reject.to_dict()),
        ("validator_reject_policy_bypass", bypass_result.to_dict()),
        ("validator_reject_unknown_key", rogue_result.to_dict()),
        ("validator_reject_tamper", tampered_result.to_dict()),
        ("validator_reject_replay", replay_result.to_dict()),
    ]


if __name__ == "__main__":
    for name, payload in demo_scenarios():
        print(f"== {name} ==")
        print(pretty(payload))
