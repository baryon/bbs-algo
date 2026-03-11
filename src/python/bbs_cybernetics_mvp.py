"""Minimal cybernetics-oriented MVP for agent feedback loops.

This module turns the memo's control-theory framing into runnable code:

Agent -> Validator -> Feedback -> Retry

It intentionally stays abstract. The goal is to show how structured feedback
acts as an error signal that helps an agent converge toward a target state.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any


@dataclass(frozen=True)
class CandidateAction:
    agent_id: str
    quality_score: int
    cost: int
    latency_ms: int
    risk_score: int
    iteration: int
    nonce: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "quality_score": self.quality_score,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "risk_score": self.risk_score,
            "iteration": self.iteration,
            "nonce": self.nonce,
        }


@dataclass(frozen=True)
class ControlPolicy:
    policy_id: str
    min_quality_score: int
    max_cost: int
    max_latency_ms: int
    max_risk_score: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "min_quality_score": self.min_quality_score,
            "max_cost": self.max_cost,
            "max_latency_ms": self.max_latency_ms,
            "max_risk_score": self.max_risk_score,
        }


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    stage: str
    reasons: tuple[str, ...]
    measurements: dict[str, int]
    deviations: dict[str, int]
    feedback_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "stage": self.stage,
            "reasons": list(self.reasons),
            "measurements": self.measurements,
            "deviations": self.deviations,
            "feedback_mode": self.feedback_mode,
        }


@dataclass(frozen=True)
class RevisionResult:
    next_action: CandidateAction | None
    requested_adjustments: dict[str, int]
    applied_adjustments: dict[str, int]
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_adjustments": self.requested_adjustments,
            "applied_adjustments": self.applied_adjustments,
            "stop_reason": self.stop_reason,
        }


class ControlValidator:
    def __init__(self, policy: ControlPolicy, feedback_mode: str = "rich") -> None:
        if feedback_mode not in {"rich", "coarse", "none"}:
            raise ValueError(f"unsupported feedback_mode: {feedback_mode}")
        self.policy = policy
        self.feedback_mode = feedback_mode

    def validate(self, candidate: CandidateAction) -> ValidationResult:
        measurements = {
            "quality_score": candidate.quality_score,
            "cost": candidate.cost,
            "latency_ms": candidate.latency_ms,
            "risk_score": candidate.risk_score,
        }
        reasons: list[str] = []
        deviations: dict[str, int] = {}

        quality_deviation = candidate.quality_score - self.policy.min_quality_score
        if quality_deviation < 0:
            reasons.append("quality_below_target")
            deviations["quality_score"] = quality_deviation

        cost_deviation = candidate.cost - self.policy.max_cost
        if cost_deviation > 0:
            reasons.append("cost_above_limit")
            deviations["cost"] = cost_deviation

        latency_deviation = candidate.latency_ms - self.policy.max_latency_ms
        if latency_deviation > 0:
            reasons.append("latency_above_limit")
            deviations["latency_ms"] = latency_deviation

        risk_deviation = candidate.risk_score - self.policy.max_risk_score
        if risk_deviation > 0:
            reasons.append("risk_above_limit")
            deviations["risk_score"] = risk_deviation

        if not reasons:
            return ValidationResult(
                accepted=True,
                stage="validator",
                reasons=(),
                measurements=measurements,
                deviations={},
                feedback_mode=self.feedback_mode,
            )

        if self.feedback_mode == "rich":
            return ValidationResult(
                accepted=False,
                stage="validator",
                reasons=tuple(reasons),
                measurements=measurements,
                deviations=deviations,
                feedback_mode=self.feedback_mode,
            )

        if self.feedback_mode == "coarse":
            return ValidationResult(
                accepted=False,
                stage="validator",
                reasons=tuple(reasons),
                measurements=measurements,
                deviations={},
                feedback_mode=self.feedback_mode,
            )

        return ValidationResult(
            accepted=False,
            stage="validator",
            reasons=(),
            measurements=measurements,
            deviations={},
            feedback_mode=self.feedback_mode,
        )


class AdaptiveAgent:
    def __init__(
        self,
        agent_id: str,
        max_quality_score: int = 90,
        min_cost: int = 60,
        min_latency_ms: int = 120,
        min_risk_score: int = 8,
    ) -> None:
        self.agent_id = agent_id
        self.max_quality_score = max_quality_score
        self.min_cost = min_cost
        self.min_latency_ms = min_latency_ms
        self.min_risk_score = min_risk_score

    def revise(
        self,
        candidate: CandidateAction,
        validation: ValidationResult,
    ) -> RevisionResult:
        if validation.accepted:
            return RevisionResult(
                next_action=None,
                requested_adjustments={},
                applied_adjustments={},
                stop_reason="accepted",
            )

        if not validation.reasons:
            return RevisionResult(
                next_action=None,
                requested_adjustments={},
                applied_adjustments={},
                stop_reason="missing_feedback",
            )

        if validation.feedback_mode == "rich" and validation.deviations:
            requested = self._rich_adjustments(validation.deviations)
        else:
            requested = self._coarse_adjustments(validation.reasons)

        next_action, applied = self._apply_adjustments(candidate, requested)
        if next_action is None:
            return RevisionResult(
                next_action=None,
                requested_adjustments=requested,
                applied_adjustments=applied,
                stop_reason="actuator_limits_reached",
            )

        return RevisionResult(
            next_action=next_action,
            requested_adjustments=requested,
            applied_adjustments=applied,
        )

    def _rich_adjustments(self, deviations: dict[str, int]) -> dict[str, int]:
        adjustments: dict[str, int] = {}
        if "quality_score" in deviations and deviations["quality_score"] < 0:
            adjustments["quality_score"] = max(
                1, math.ceil(abs(deviations["quality_score"]) * 0.6)
            )
        if "cost" in deviations and deviations["cost"] > 0:
            adjustments["cost"] = -max(1, math.ceil(deviations["cost"] * 0.6))
        if "latency_ms" in deviations and deviations["latency_ms"] > 0:
            adjustments["latency_ms"] = -max(
                1, math.ceil(deviations["latency_ms"] * 0.6)
            )
        if "risk_score" in deviations and deviations["risk_score"] > 0:
            adjustments["risk_score"] = -max(
                1, math.ceil(deviations["risk_score"] * 0.6)
            )
        return adjustments

    def _coarse_adjustments(self, reasons: tuple[str, ...]) -> dict[str, int]:
        adjustments: dict[str, int] = {}
        if "quality_below_target" in reasons:
            adjustments["quality_score"] = 6
        if "cost_above_limit" in reasons:
            adjustments["cost"] = -8
        if "latency_above_limit" in reasons:
            adjustments["latency_ms"] = -30
        if "risk_above_limit" in reasons:
            adjustments["risk_score"] = -4
        return adjustments

    def _apply_adjustments(
        self,
        candidate: CandidateAction,
        requested: dict[str, int],
    ) -> tuple[CandidateAction | None, dict[str, int]]:
        next_quality = min(
            self.max_quality_score,
            max(0, candidate.quality_score + requested.get("quality_score", 0)),
        )
        next_cost = max(self.min_cost, candidate.cost + requested.get("cost", 0))
        next_latency = max(
            self.min_latency_ms,
            candidate.latency_ms + requested.get("latency_ms", 0),
        )
        next_risk = max(
            self.min_risk_score,
            candidate.risk_score + requested.get("risk_score", 0),
        )

        applied = {
            "quality_score": next_quality - candidate.quality_score,
            "cost": next_cost - candidate.cost,
            "latency_ms": next_latency - candidate.latency_ms,
            "risk_score": next_risk - candidate.risk_score,
        }
        applied = {key: value for key, value in applied.items() if value != 0}
        if not applied:
            return None, {}

        return (
            CandidateAction(
                agent_id=candidate.agent_id,
                quality_score=next_quality,
                cost=next_cost,
                latency_ms=next_latency,
                risk_score=next_risk,
                iteration=candidate.iteration + 1,
                nonce=candidate.nonce,
            ),
            applied,
        )


def pretty(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


def simulate_control_loop(
    scenario_name: str,
    policy: ControlPolicy,
    validator: ControlValidator,
    agent: AdaptiveAgent,
    initial_action: CandidateAction,
    max_iterations: int,
) -> dict[str, Any]:
    history: list[dict[str, Any]] = []
    current = initial_action
    stopped_reason = "max_iterations_reached"

    for _ in range(max_iterations):
        validation = validator.validate(current)
        revision = agent.revise(current, validation)
        history.append(
            {
                "iteration": current.iteration,
                "candidate": current.to_dict(),
                "validation": validation.to_dict(),
                "adjustments": revision.to_dict(),
            }
        )

        if validation.accepted:
            stopped_reason = "accepted"
            break

        if revision.next_action is None:
            stopped_reason = revision.stop_reason or "stopped"
            break

        current = revision.next_action

    final_validation = history[-1]["validation"]
    return {
        "scenario": scenario_name,
        "policy": policy.to_dict(),
        "initial_action": initial_action.to_dict(),
        "history": history,
        "final_result": {
            "accepted": bool(final_validation["accepted"]),
            "iterations_recorded": len(history),
            "stopped_reason": stopped_reason,
            "final_candidate": history[-1]["candidate"],
            "final_validation": final_validation,
        },
    }


def demo_scenarios() -> list[tuple[str, dict[str, Any]]]:
    agent = AdaptiveAgent(agent_id="agent_cybernetics_bot")

    converging_policy = ControlPolicy(
        policy_id="cybernetics-balanced-target-v1",
        min_quality_score=80,
        max_cost=100,
        max_latency_ms=250,
        max_risk_score=20,
    )
    initial_action = CandidateAction(
        agent_id="agent_cybernetics_bot",
        quality_score=52,
        cost=145,
        latency_ms=360,
        risk_score=33,
        iteration=0,
        nonce="cy-001",
    )

    unreachable_policy = ControlPolicy(
        policy_id="cybernetics-unreachable-target-v1",
        min_quality_score=95,
        max_cost=40,
        max_latency_ms=80,
        max_risk_score=5,
    )
    unreachable_initial = CandidateAction(
        agent_id="agent_cybernetics_bot",
        quality_score=70,
        cost=100,
        latency_ms=200,
        risk_score=20,
        iteration=0,
        nonce="cy-002",
    )

    return [
        (
            "converges_with_structured_feedback",
            simulate_control_loop(
                scenario_name="converges_with_structured_feedback",
                policy=converging_policy,
                validator=ControlValidator(converging_policy, feedback_mode="rich"),
                agent=agent,
                initial_action=initial_action,
                max_iterations=6,
            ),
        ),
        (
            "fails_with_coarse_feedback",
            simulate_control_loop(
                scenario_name="fails_with_coarse_feedback",
                policy=converging_policy,
                validator=ControlValidator(converging_policy, feedback_mode="coarse"),
                agent=agent,
                initial_action=initial_action,
                max_iterations=4,
            ),
        ),
        (
            "fails_with_unreachable_target",
            simulate_control_loop(
                scenario_name="fails_with_unreachable_target",
                policy=unreachable_policy,
                validator=ControlValidator(unreachable_policy, feedback_mode="rich"),
                agent=agent,
                initial_action=unreachable_initial,
                max_iterations=6,
            ),
        ),
        (
            "stops_without_feedback_channel",
            simulate_control_loop(
                scenario_name="stops_without_feedback_channel",
                policy=converging_policy,
                validator=ControlValidator(converging_policy, feedback_mode="none"),
                agent=agent,
                initial_action=initial_action,
                max_iterations=3,
            ),
        ),
    ]


if __name__ == "__main__":
    for name, payload in demo_scenarios():
        print(f"== {name} ==")
        print(pretty(payload))
