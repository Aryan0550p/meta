from __future__ import annotations

import copy
from typing import Any, Dict, Tuple

from .graders import compute_task_score, reward_components
from .models import BugStatus, PipelineAction, PipelineObservation, PipelineReward, PipelineState
from .tasks import TASKS, list_task_ids


class DataPipelineDebuggerEnv:
    def __init__(self, default_task_id: str = "easy_schema_mismatch") -> None:
        if default_task_id not in TASKS:
            raise ValueError(f"Unknown default task_id: {default_task_id}")
        self.default_task_id = default_task_id
        self._state: PipelineState | None = None
        self.reset(default_task_id)

    def reset(self, task_id: str | None = None) -> PipelineObservation:
        selected = task_id or self.default_task_id
        if selected not in TASKS:
            raise ValueError(f"Unknown task_id: {selected}")

        spec = TASKS[selected]
        bug_status = {
            b["bug_id"]: BugStatus(
                bug_id=b["bug_id"],
                title=b["title"],
                stage=b["stage"],
                severity=b["severity"],
            )
            for b in spec["bugs"]
        }

        self._state = PipelineState(
            task_id=selected,
            objective=spec["objective"],
            step_count=0,
            max_steps=spec["max_steps"],
            done=False,
            total_reward=0.0,
            bug_status=bug_status,
            action_history=[],
        )
        return self._to_observation("Environment reset")

    def state(self) -> PipelineState:
        if self._state is None:
            raise RuntimeError("Environment not initialized")
        return copy.deepcopy(self._state)

    def step(self, action: PipelineAction) -> Tuple[PipelineObservation, PipelineReward, bool, Dict[str, Any]]:
        if self._state is None:
            raise RuntimeError("Environment not initialized")
        if self._state.done:
            obs = self._to_observation("Episode already finished")
            reward = PipelineReward(value=0.0, components={"done": 0.0}, rationale="No reward after done")
            return obs, reward, True, {"task_score": compute_task_score(self._state)}

        self._state.step_count += 1
        discovered = False
        explained = False
        fixed = False
        invalid = False
        repeated = False
        latest_event = "Action processed"

        action_dict = action.model_dump()

        if action.action_type.value == "inspect_stage":
            stage = (action.stage or "").strip().lower()
            if not stage:
                invalid = True
                latest_event = "inspect_stage requires stage"
            else:
                changed = False
                for bug in self._state.bug_status.values():
                    if bug.stage == stage and not bug.discovered:
                        bug.discovered = True
                        discovered = True
                        changed = True
                if not changed:
                    repeated = True
                latest_event = f"Inspected stage: {stage}"

        elif action.action_type.value == "run_validation":
            rule = (action.rule or "").strip().lower()
            if not rule:
                invalid = True
                latest_event = "run_validation requires rule"
            else:
                matched = False
                for bug in self._state.bug_status.values():
                    if not bug.discovered and self._rule_can_find_bug(rule, bug.bug_id):
                        bug.discovered = True
                        discovered = True
                        matched = True
                if not matched:
                    repeated = True
                latest_event = f"Validation executed: {rule}"

        elif action.action_type.value == "explain_bug":
            if not action.bug_id or not action.explanation:
                invalid = True
                latest_event = "explain_bug requires bug_id and explanation"
            else:
                bug = self._state.bug_status.get(action.bug_id)
                if bug is None:
                    invalid = True
                    latest_event = f"Unknown bug_id: {action.bug_id}"
                elif bug.explained:
                    repeated = True
                    latest_event = f"Bug already explained: {action.bug_id}"
                else:
                    if self._valid_explanation(self._state.task_id, action.bug_id, action.explanation):
                        bug.explained = True
                        explained = True
                        latest_event = f"Explanation accepted for {action.bug_id}"
                    else:
                        invalid = True
                        latest_event = f"Explanation not specific enough for {action.bug_id}"

        elif action.action_type.value == "apply_fix":
            if not action.bug_id:
                invalid = True
                latest_event = "apply_fix requires bug_id"
            else:
                bug = self._state.bug_status.get(action.bug_id)
                if bug is None:
                    invalid = True
                    latest_event = f"Unknown bug_id: {action.bug_id}"
                elif bug.fixed:
                    repeated = True
                    latest_event = f"Bug already fixed: {action.bug_id}"
                else:
                    if bug.discovered:
                        bug.fixed = True
                        fixed = True
                        latest_event = f"Fix applied for {action.bug_id}"
                    else:
                        invalid = True
                        latest_event = f"Discover bug before fixing: {action.bug_id}"

        elif action.action_type.value == "finish":
            self._state.done = True
            latest_event = "Agent chose to finish"

        else:
            invalid = True
            latest_event = f"Unsupported action: {action.action_type.value}"

        action_sig = str(action_dict)
        if any(h.get("signature") == action_sig for h in self._state.action_history):
            repeated = True

        done_bonus = 0.0
        if self._all_critical_done() and not self._state.done:
            self._state.done = True
            done_bonus = 0.08
            latest_event = "All bugs fixed and explained"

        if self._state.step_count >= self._state.max_steps:
            self._state.done = True
            latest_event = "Max steps reached"

        components = reward_components(discovered, explained, fixed, invalid, repeated, done_bonus)
        step_reward = max(0.0, min(1.0, sum(components.values())))
        self._state.total_reward += step_reward

        self._state.action_history.append(
            {
                "signature": action_sig,
                "invalid": invalid,
                "repeat": repeated,
                "step_reward": step_reward,
                "event": latest_event,
            }
        )

        obs = self._to_observation(latest_event)
        reward = PipelineReward(
            value=step_reward,
            components=components,
            rationale=latest_event,
        )
        info = {
            "task_score": compute_task_score(self._state),
            "task_id": self._state.task_id,
            "step_count": self._state.step_count,
            "available_tasks": list_task_ids(),
        }
        return obs, reward, self._state.done, info

    def _all_critical_done(self) -> bool:
        assert self._state is not None
        bugs = list(self._state.bug_status.values())
        if not bugs:
            return False
        return all(b.fixed and b.explained for b in bugs)

    def _to_observation(self, event: str) -> PipelineObservation:
        assert self._state is not None
        spec = TASKS[self._state.task_id]
        score_hint = compute_task_score(self._state)
        return PipelineObservation(
            task_id=self._state.task_id,
            step_count=self._state.step_count,
            max_steps=self._state.max_steps,
            objective=self._state.objective,
            latest_event=event,
            visible_stages=spec["stages"],
            visible_rules=spec["rules"],
            bugs=[copy.deepcopy(b) for b in self._state.bug_status.values()],
            running_score_hint=score_hint,
        )

    @staticmethod
    def _rule_can_find_bug(rule: str, bug_id: str) -> bool:
        mapping = {
            "E1": {"schema_check", "type_check"},
            "M1": {"null_check", "business_rule_check"},
            "M2": {"type_check", "null_check"},
            "H1": {"window_consistency_check", "type_check"},
            "H2": {"idempotency_check", "business_rule_check"},
            "H3": {"business_rule_check", "type_check"},
        }
        return rule in mapping.get(bug_id, set())

    @staticmethod
    def _valid_explanation(task_id: str, bug_id: str, explanation: str) -> bool:
        explanation_l = explanation.lower()
        task = TASKS[task_id]
        for bug in task["bugs"]:
            if bug["bug_id"] == bug_id:
                return any(token in explanation_l for token in bug["valid_explanations"])
        return False
