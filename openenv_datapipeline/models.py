from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    INSPECT_STAGE = "inspect_stage"
    RUN_VALIDATION = "run_validation"
    EXPLAIN_BUG = "explain_bug"
    APPLY_FIX = "apply_fix"
    FINISH = "finish"


class PipelineAction(BaseModel):
    action_type: ActionType
    stage: Optional[str] = None
    rule: Optional[str] = None
    bug_id: Optional[str] = None
    explanation: Optional[str] = None


class BugStatus(BaseModel):
    bug_id: str
    title: str
    stage: str
    severity: Literal["low", "medium", "high"]
    discovered: bool = False
    explained: bool = False
    fixed: bool = False


class PipelineObservation(BaseModel):
    task_id: str
    step_count: int
    max_steps: int
    objective: str
    latest_event: str
    visible_stages: List[str]
    visible_rules: List[str]
    bugs: List[BugStatus]
    running_score_hint: float = Field(ge=0.0, le=1.0)


class PipelineReward(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    components: Dict[str, float] = Field(default_factory=dict)
    rationale: str


class PipelineState(BaseModel):
    task_id: str
    objective: str
    step_count: int
    max_steps: int
    done: bool
    total_reward: float = 0.0
    bug_status: Dict[str, BugStatus]
    action_history: List[Dict[str, Any]] = Field(default_factory=list)
