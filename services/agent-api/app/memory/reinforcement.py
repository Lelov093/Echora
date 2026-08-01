"""Memory reinforcement and Beta confidence calibration."""

from app.core.algorithm_contract import MEMORY_REINFORCEMENT_CONTRACT, clamp01, contract_trace
from app.memory.decay import MEMORY_LIFECYCLE_VERSION


def compute_reinforcement_delta(
    successful_recall: bool = False,
    user_confirmed: bool = False,
    used_in_growth: bool = False,
    used_in_presence: bool = False,
    repeated_topic: bool = False,
) -> float:
    weights = MEMORY_REINFORCEMENT_CONTRACT["weights"]
    return sum(
        weights[name] * (1.0 if enabled else 0.0)
        for name, enabled in {
            "successful_recall": successful_recall,
            "user_confirmed": user_confirmed,
            "used_in_growth": used_in_growth,
            "used_in_presence": used_in_presence,
            "repeated_topic": repeated_topic,
        }.items()
    )


def apply_reinforcement(
    current_strength: float,
    successful_recall: bool = False,
    user_confirmed: bool = False,
    used_in_growth: bool = False,
    used_in_presence: bool = False,
    repeated_topic: bool = False,
) -> dict:
    delta = compute_reinforcement_delta(
        successful_recall,
        user_confirmed,
        used_in_growth,
        used_in_presence,
        repeated_topic,
    )
    new_strength = clamp01(clamp01(current_strength) + delta)
    return {
        "previous_strength": round(current_strength, 6),
        "new_strength": round(new_strength, 6),
        "delta": round(delta, 6),
        "factors": {
            "successful_recall": successful_recall,
            "user_confirmed": user_confirmed,
            "used_in_growth": used_in_growth,
            "used_in_presence": used_in_presence,
            "repeated_topic": repeated_topic,
        },
        "algorithm": contract_trace(MEMORY_REINFORCEMENT_CONTRACT),
        "algorithm_version": MEMORY_LIFECYCLE_VERSION,
    }


def compute_beta_confidence(
    *,
    positive_confirmations: int = 0,
    helpful_count: int = 0,
    accepted_count: int = 0,
    irrelevant_count: int = 0,
    outdated_count: int = 0,
    wrong_count: int = 0,
    rejected_count: int = 0,
    prior_alpha: float = 2.0,
    prior_beta: float = 2.0,
) -> dict:
    alpha = max(0.001, float(prior_alpha))
    beta = max(0.001, float(prior_beta))
    alpha += max(0, positive_confirmations)
    alpha += max(0, helpful_count)
    alpha += 0.5 * max(0, accepted_count)
    beta += 0.5 * max(0, irrelevant_count)
    beta += max(0, outdated_count)
    beta += 2.0 * max(0, wrong_count)
    beta += max(0, rejected_count)
    confidence = alpha / (alpha + beta)
    return {
        "alpha": round(alpha, 6),
        "beta": round(beta, 6),
        "confidence": round(clamp01(confidence), 6),
        "prior_alpha": prior_alpha,
        "prior_beta": prior_beta,
        "algorithm_version": MEMORY_LIFECYCLE_VERSION,
    }


def compute_negative_feedback_penalty(
    *,
    new_irrelevant: int = 0,
    new_outdated: int = 0,
    new_wrong: int = 0,
) -> dict:
    penalty = (
        0.05 * max(0, new_irrelevant)
        + 0.08 * max(0, new_outdated)
        + 0.20 * max(0, new_wrong)
    )
    return {
        "strength_penalty": round(min(1.0, penalty), 6),
        "new_irrelevant": max(0, new_irrelevant),
        "new_outdated": max(0, new_outdated),
        "new_wrong": max(0, new_wrong),
        "algorithm_version": MEMORY_LIFECYCLE_VERSION,
    }
