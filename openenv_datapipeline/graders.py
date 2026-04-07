from __future__ import annotations

from typing import Dict

from .models import PipelineState


def compute_task_score(state: PipelineState) -> float:
    bugs = list(state.bug_status.values())
    if not bugs:
        return 0.0

    discovered_ratio = sum(1 for b in bugs if b.discovered) / len(bugs)
    explained_ratio = sum(1 for b in bugs if b.explained) / len(bugs)
    fixed_ratio = sum(1 for b in bugs if b.fixed) / len(bugs)

    # Weighted grading favors fixed and explained outcomes over mere discovery.
    raw = 0.20 * discovered_ratio + 0.30 * explained_ratio + 0.50 * fixed_ratio

    invalid_actions = sum(1 for a in state.action_history if a.get("invalid", False))
    repeat_actions = sum(1 for a in state.action_history if a.get("repeat", False))
    penalties = min(0.20, invalid_actions * 0.03 + repeat_actions * 0.01)

    return max(0.0, min(1.0, raw - penalties))


def reward_components(
    discovered: bool,
    explained: bool,
    fixed: bool,
    invalid: bool,
    repeated: bool,
    done_bonus: float,
) -> Dict[str, float]:
    components: Dict[str, float] = {
        "discovered": 0.10 if discovered else 0.0,
        "explained": 0.18 if explained else 0.0,
        "fixed": 0.24 if fixed else 0.0,
        "invalid": -0.08 if invalid else 0.0,
        "repeat": -0.03 if repeated else 0.0,
        "step_cost": -0.01,
        "done_bonus": done_bonus,
    }
    return components
