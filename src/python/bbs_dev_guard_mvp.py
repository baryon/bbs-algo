"""Minimal development-guard MVP for db_update and file_rm actions.

This module extends the same control flow used in the payment MVP:

Agent -> Action -> Sign -> Validator -> Execute

It is still a concept-validation implementation:

- it uses Ed25519 signatures from `cryptography`
- policy checks are explicit validator logic, not zero-knowledge proofs
- validator rechecks policy instead of verifying a ZK statement
"""

from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath
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


def normalize_posix_path(path: str) -> str:
    normalized = str(PurePosixPath(path))
    if not normalized.startswith("/"):
        return normalized
    return normalized


def path_under_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


@dataclass(frozen=True)
class DbUpdateAction:
    agent_id: str
    env: str
    table: str
    fields: tuple[str, ...]
    where_scope: str
    row_limit: int
    epoch: int
    nonce: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "env": self.env,
            "table": self.table,
            "fields": list(self.fields),
            "where_scope": self.where_scope,
            "row_limit": self.row_limit,
            "epoch": self.epoch,
            "nonce": self.nonce,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class FileRemoveAction:
    agent_id: str
    path: str
    recursive: bool
    epoch: int
    nonce: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "path": self.path,
            "recursive": self.recursive,
            "epoch": self.epoch,
            "nonce": self.nonce,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DbUpdatePolicy:
    policy_id: str
    allowed_envs: tuple[str, ...]
    allowed_tables: tuple[str, ...]
    allowed_fields: tuple[str, ...]
    allowed_where_scopes: tuple[str, ...]
    max_row_limit: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "allowed_envs": list(self.allowed_envs),
            "allowed_tables": list(self.allowed_tables),
            "allowed_fields": list(self.allowed_fields),
            "allowed_where_scopes": list(self.allowed_where_scopes),
            "max_row_limit": self.max_row_limit,
        }

    def fingerprint(self) -> str:
        return sha256_hex(canonical_json(self.to_dict()))

    def evaluate(self, action: DbUpdateAction) -> list[str]:
        reasons: list[str] = []
        if action.env not in self.allowed_envs:
            reasons.append("db_env_not_allowed")
        if action.table not in self.allowed_tables:
            reasons.append("db_table_not_allowed")
        disallowed_fields = [
            field for field in action.fields if field not in self.allowed_fields
        ]
        if disallowed_fields:
            reasons.append("db_field_not_allowed")
        if action.where_scope not in self.allowed_where_scopes:
            reasons.append("db_where_scope_not_allowed")
        if action.row_limit <= 0:
            reasons.append("db_row_limit_must_be_positive")
        if action.row_limit > self.max_row_limit:
            reasons.append("db_row_limit_exceeds_limit")
        return reasons


@dataclass(frozen=True)
class FileRemovePolicy:
    policy_id: str
    allowed_prefixes: tuple[str, ...]
    blocked_prefixes: tuple[str, ...]
    allow_recursive: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "allowed_prefixes": list(self.allowed_prefixes),
            "blocked_prefixes": list(self.blocked_prefixes),
            "allow_recursive": self.allow_recursive,
        }

    def fingerprint(self) -> str:
        return sha256_hex(canonical_json(self.to_dict()))

    def evaluate(self, action: FileRemoveAction) -> list[str]:
        reasons: list[str] = []
        normalized = normalize_posix_path(action.path)
        if not normalized.startswith("/"):
            reasons.append("file_path_must_be_absolute")
            return reasons
        if any(path_under_prefix(normalized, prefix) for prefix in self.blocked_prefixes):
            reasons.append("file_path_blocked")
        if not any(
            path_under_prefix(normalized, prefix) for prefix in self.allowed_prefixes
        ):
            reasons.append("file_path_outside_allowed_prefixes")
        if action.recursive and not self.allow_recursive:
            reasons.append("file_recursive_remove_not_allowed")
        return reasons


@dataclass(frozen=True)
class SignedDevRequest:
    agent_id: str
    action_kind: str
    public_key_pem: str
    policy_fingerprint: str
    action_payload: dict[str, Any]
    signature_b64: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "action_kind": self.action_kind,
            "public_key_pem": self.public_key_pem,
            "policy_fingerprint": self.policy_fingerprint,
            "action_payload": self.action_payload,
            "signature_b64": self.signature_b64,
        }


@dataclass(frozen=True)
class SigningResult:
    ok: bool
    stage: str
    reasons: tuple[str, ...] = ()
    request: SignedDevRequest | None = None

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
class RegisteredDevAgent:
    public_key_pem: str
    db_policy: DbUpdatePolicy
    file_policy: FileRemovePolicy


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
    action_kind: str,
    action_payload: dict[str, Any],
    policy_fingerprint: str,
) -> bytes:
    payload = {
        "action_kind": action_kind,
        "action_payload": action_payload,
        "policy_fingerprint": policy_fingerprint,
    }
    return canonical_json(payload)


class DevGuardSigner:
    def __init__(
        self,
        agent_id: str,
        private_key: Ed25519PrivateKey,
        public_key_pem: str,
        db_policy: DbUpdatePolicy,
        file_policy: FileRemovePolicy,
    ) -> None:
        self.agent_id = agent_id
        self.private_key = private_key
        self.public_key_pem = public_key_pem
        self.db_policy = db_policy
        self.file_policy = file_policy

    def sign_db_update(self, action: DbUpdateAction) -> SigningResult:
        reasons: list[str] = []
        if action.agent_id != self.agent_id:
            reasons.append("agent_id_mismatch")
        reasons.extend(self.db_policy.evaluate(action))
        if reasons:
            return SigningResult(ok=False, stage="signer", reasons=tuple(reasons))

        payload = action.to_dict()
        policy_fingerprint = self.db_policy.fingerprint()
        signature = self.private_key.sign(
            build_signing_message("db_update", payload, policy_fingerprint)
        )
        return SigningResult(
            ok=True,
            stage="signer",
            request=SignedDevRequest(
                agent_id=self.agent_id,
                action_kind="db_update",
                public_key_pem=self.public_key_pem,
                policy_fingerprint=policy_fingerprint,
                action_payload=payload,
                signature_b64=b64encode(signature).decode("ascii"),
            ),
        )

    def sign_file_remove(self, action: FileRemoveAction) -> SigningResult:
        reasons: list[str] = []
        if action.agent_id != self.agent_id:
            reasons.append("agent_id_mismatch")
        reasons.extend(self.file_policy.evaluate(action))
        if reasons:
            return SigningResult(ok=False, stage="signer", reasons=tuple(reasons))

        payload = action.to_dict()
        policy_fingerprint = self.file_policy.fingerprint()
        signature = self.private_key.sign(
            build_signing_message("file_rm", payload, policy_fingerprint)
        )
        return SigningResult(
            ok=True,
            stage="signer",
            request=SignedDevRequest(
                agent_id=self.agent_id,
                action_kind="file_rm",
                public_key_pem=self.public_key_pem,
                policy_fingerprint=policy_fingerprint,
                action_payload=payload,
                signature_b64=b64encode(signature).decode("ascii"),
            ),
        )


class DevGuardValidator:
    def __init__(self, registry: dict[str, RegisteredDevAgent]) -> None:
        self.registry = registry
        self._used_nonces: set[tuple[str, str]] = set()

    def validate(self, request: SignedDevRequest) -> ValidationResult:
        registered = self.registry.get(request.agent_id)
        if registered is None:
            return ValidationResult(
                accepted=False,
                stage="validator",
                reasons=("unknown_agent",),
            )

        reasons: list[str] = []
        if request.public_key_pem != registered.public_key_pem:
            reasons.append("public_key_not_registered")

        expected_policy_fingerprint: str | None = None
        policy_reasons: list[str] = []

        if request.action_kind == "db_update":
            expected_policy_fingerprint = registered.db_policy.fingerprint()
            action = DbUpdateAction(
                agent_id=str(request.action_payload["agent_id"]),
                env=str(request.action_payload["env"]),
                table=str(request.action_payload["table"]),
                fields=tuple(request.action_payload["fields"]),
                where_scope=str(request.action_payload["where_scope"]),
                row_limit=int(request.action_payload["row_limit"]),
                epoch=int(request.action_payload["epoch"]),
                nonce=str(request.action_payload["nonce"]),
                reason=str(request.action_payload.get("reason", "")),
            )
            if action.agent_id != request.agent_id:
                reasons.append("request_agent_id_mismatch")
            policy_reasons = registered.db_policy.evaluate(action)
            nonce = action.nonce
        elif request.action_kind == "file_rm":
            expected_policy_fingerprint = registered.file_policy.fingerprint()
            action = FileRemoveAction(
                agent_id=str(request.action_payload["agent_id"]),
                path=str(request.action_payload["path"]),
                recursive=bool(request.action_payload["recursive"]),
                epoch=int(request.action_payload["epoch"]),
                nonce=str(request.action_payload["nonce"]),
                reason=str(request.action_payload.get("reason", "")),
            )
            if action.agent_id != request.agent_id:
                reasons.append("request_agent_id_mismatch")
            policy_reasons = registered.file_policy.evaluate(action)
            nonce = action.nonce
        else:
            reasons.append("unknown_action_kind")
            nonce = ""

        if expected_policy_fingerprint is not None:
            if request.policy_fingerprint != expected_policy_fingerprint:
                reasons.append("policy_fingerprint_mismatch")

        if reasons:
            return ValidationResult(
                accepted=False,
                stage="validator",
                reasons=tuple(reasons),
            )

        public_key = serialization.load_pem_public_key(
            request.public_key_pem.encode("ascii")
        )
        assert isinstance(public_key, Ed25519PublicKey)

        try:
            public_key.verify(
                b64decode(request.signature_b64),
                build_signing_message(
                    request.action_kind,
                    request.action_payload,
                    request.policy_fingerprint,
                ),
            )
        except InvalidSignature:
            return ValidationResult(
                accepted=False,
                stage="validator",
                reasons=("invalid_signature",),
            )

        if policy_reasons:
            return ValidationResult(
                accepted=False,
                stage="validator",
                reasons=tuple(policy_reasons),
            )

        nonce_key = (request.agent_id, nonce)
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
    action_kind: str,
    policy_fingerprint: str,
    action_payload: dict[str, Any],
) -> SignedDevRequest:
    signature = private_key.sign(
        build_signing_message(action_kind, action_payload, policy_fingerprint)
    )
    return SignedDevRequest(
        agent_id=agent_id,
        action_kind=action_kind,
        public_key_pem=public_key_pem,
        policy_fingerprint=policy_fingerprint,
        action_payload=action_payload,
        signature_b64=b64encode(signature).decode("ascii"),
    )


def pretty(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


def demo_scenarios() -> list[tuple[str, dict[str, Any]]]:
    db_policy = DbUpdatePolicy(
        policy_id="db-staging-safe-update-v1",
        allowed_envs=("staging",),
        allowed_tables=("feature_flags", "task_runs"),
        allowed_fields=("enabled", "status", "updated_by"),
        allowed_where_scopes=("id_eq", "job_id_eq"),
        max_row_limit=1,
    )
    file_policy = FileRemovePolicy(
        policy_id="file-rm-sandbox-v1",
        allowed_prefixes=("/workspace/sandbox", "/workspace/tmp"),
        blocked_prefixes=("/etc", "/usr", "/bin", "/var/lib"),
        allow_recursive=False,
    )

    trusted_private_key, trusted_public_key_pem = generate_keypair()
    rogue_private_key, rogue_public_key_pem = generate_keypair()

    signer = DevGuardSigner(
        agent_id="agent_dev_bot",
        private_key=trusted_private_key,
        public_key_pem=trusted_public_key_pem,
        db_policy=db_policy,
        file_policy=file_policy,
    )
    validator = DevGuardValidator(
        registry={
            "agent_dev_bot": RegisteredDevAgent(
                public_key_pem=trusted_public_key_pem,
                db_policy=db_policy,
                file_policy=file_policy,
            )
        }
    )

    valid_db_action = DbUpdateAction(
        agent_id="agent_dev_bot",
        env="staging",
        table="feature_flags",
        fields=("enabled",),
        where_scope="id_eq",
        row_limit=1,
        epoch=202603111330,
        nonce="db-001",
        reason="toggle safe feature flag in staging",
    )
    invalid_db_action = DbUpdateAction(
        agent_id="agent_dev_bot",
        env="production",
        table="users",
        fields=("role",),
        where_scope="all_rows",
        row_limit=50,
        epoch=202603111331,
        nonce="db-002",
        reason="dangerous production bulk update",
    )
    valid_file_action = FileRemoveAction(
        agent_id="agent_dev_bot",
        path="/workspace/sandbox/build/output.tmp",
        recursive=False,
        epoch=202603111332,
        nonce="fs-001",
        reason="cleanup sandbox artifact",
    )
    invalid_file_action = FileRemoveAction(
        agent_id="agent_dev_bot",
        path="/etc/passwd",
        recursive=False,
        epoch=202603111333,
        nonce="fs-002",
        reason="dangerous system file remove",
    )

    signed_valid_db = signer.sign_db_update(valid_db_action)
    assert signed_valid_db.request is not None
    valid_db_result = validator.validate(signed_valid_db.request)

    signer_reject_db = signer.sign_db_update(invalid_db_action)

    bypass_db_request = sign_without_policy_check(
        private_key=trusted_private_key,
        public_key_pem=trusted_public_key_pem,
        agent_id="agent_dev_bot",
        action_kind="db_update",
        policy_fingerprint=db_policy.fingerprint(),
        action_payload=invalid_db_action.to_dict(),
    )
    bypass_db_result = validator.validate(bypass_db_request)

    signed_valid_file = signer.sign_file_remove(valid_file_action)
    assert signed_valid_file.request is not None
    valid_file_result = validator.validate(signed_valid_file.request)

    signer_reject_file = signer.sign_file_remove(invalid_file_action)

    bypass_file_request = sign_without_policy_check(
        private_key=trusted_private_key,
        public_key_pem=trusted_public_key_pem,
        agent_id="agent_dev_bot",
        action_kind="file_rm",
        policy_fingerprint=file_policy.fingerprint(),
        action_payload=invalid_file_action.to_dict(),
    )
    bypass_file_result = validator.validate(bypass_file_request)

    rogue_request = sign_without_policy_check(
        private_key=rogue_private_key,
        public_key_pem=rogue_public_key_pem,
        agent_id="agent_dev_bot",
        action_kind="file_rm",
        policy_fingerprint=file_policy.fingerprint(),
        action_payload=valid_file_action.to_dict(),
    )
    rogue_result = validator.validate(rogue_request)

    replay_result = validator.validate(signed_valid_file.request)

    return [
        ("valid_db_update", valid_db_result.to_dict()),
        ("signer_reject_db_update", signer_reject_db.to_dict()),
        ("validator_reject_db_policy_bypass", bypass_db_result.to_dict()),
        ("valid_file_rm", valid_file_result.to_dict()),
        ("signer_reject_file_rm", signer_reject_file.to_dict()),
        ("validator_reject_file_policy_bypass", bypass_file_result.to_dict()),
        ("validator_reject_unknown_key", rogue_result.to_dict()),
        ("validator_reject_replay", replay_result.to_dict()),
    ]


if __name__ == "__main__":
    for name, payload in demo_scenarios():
        print(f"== {name} ==")
        print(pretty(payload))
