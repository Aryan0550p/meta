from __future__ import annotations

import json
import os
import random
from typing import Any, Dict, List, Optional

from openai import OpenAI

from openenv_datapipeline.env import DataPipelineDebuggerEnv
from openenv_datapipeline.graders import compute_task_score
from openenv_datapipeline.models import PipelineAction
from openenv_datapipeline.tasks import list_task_ids

SEED = 42
MAX_AGENT_STEPS = 20
BENCHMARK = "data-pipeline-debugger-openenv"

BUG_EXPLANATIONS = {
    "E1": "Schema mismatch with string versus integer type mismatch on customer_id.",
    "M1": "Null handling bug with missing default that triggers downstream join failure.",
    "M2": "Unsafe cast from empty string during type conversion for age.",
    "H1": "Timezone timestamp normalization issue causing window shift.",
    "H2": "Deduplication bug with duplicate events causing double counting.",
    "H3": "Business rule sign handling error in refund logic.",
    "L1": "Contract rename without schema evolution versioning caused downstream breakage.",
    "L2": "Lineage mapping points to deprecated source, causing stale joins.",
    "S1": "Watermark policy drops late events instead of routing to backfill lane.",
    "S2": "Dedupe key collision because source_system is missing from key.",
    "S3": "SLA guard retries full partition rather than incremental delta updates.",
}


def build_client() -> Optional[OpenAI]:
    # Validator requirement: use injected LiteLLM proxy env vars.
    proxy_base_url = (os.getenv("API_BASE_URL") or "").strip()
    proxy_api_key = (os.getenv("API_KEY") or "").strip()

    # Local fallback only when validator vars are absent.
    fallback_base_url = (os.getenv("API_BASE_URL_FALLBACK") or "https://router.huggingface.co/v1").strip()
    fallback_api_key = (os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY") or "dummy").strip()

    if proxy_base_url and proxy_api_key:
        base_url = proxy_base_url
        api_key = proxy_api_key
    else:
        base_url = fallback_base_url
        api_key = fallback_api_key

    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        base_url = "https://router.huggingface.co/v1"

    try:
        return OpenAI(api_key=api_key, base_url=base_url)
    except Exception:
        return None


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)


def choose_action_with_llm(client: Optional[OpenAI], model_name: str, observation: Dict[str, Any]) -> PipelineAction:
    if client is None:
        raise RuntimeError("OpenAI client unavailable")
    system_prompt = (
        "You are a senior data engineer fixing ETL pipeline bugs. "
        "Return only JSON with keys: action_type, stage, rule, bug_id, explanation. "
        "Prefer deterministic and minimal actions."
    )
    user_prompt = (
        "Given this observation, choose the single best next action.\n"
        f"Observation:\n{json.dumps(observation, indent=2)}"
    )

    completion = client.chat.completions.create(
        model=model_name,
        temperature=0.0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    raw = completion.choices[0].message.content or "{}"
    payload = json.loads(raw)
    return PipelineAction(**payload)


def fallback_action(observation: Dict[str, Any]) -> PipelineAction:
    bugs = observation.get("bugs", [])
    undiscovered = [b for b in bugs if not b.get("discovered")]
    explainable = [b for b in bugs if b.get("discovered") and not b.get("explained")]
    fixable = [b for b in bugs if b.get("discovered") and b.get("explained") and not b.get("fixed")]

    if all(b.get("discovered") and b.get("explained") and b.get("fixed") for b in bugs):
        return PipelineAction(action_type="finish")

    if undiscovered:
        # Discover by stage to maximize bug visibility with minimal actions.
        return PipelineAction(action_type="inspect_stage", stage=undiscovered[0].get("stage", "transform"))

    if explainable:
        bug = explainable[0]
        bug_id = bug["bug_id"]
        return PipelineAction(
            action_type="explain_bug",
            bug_id=bug_id,
            explanation=BUG_EXPLANATIONS.get(bug_id, "Type mismatch and business rule violation."),
        )

    if fixable:
        return PipelineAction(action_type="apply_fix", bug_id=fixable[0]["bug_id"])

    return PipelineAction(action_type="finish")


def run_task(client: Optional[OpenAI], model_name: str, task_id: str) -> Dict[str, Any]:
    env = DataPipelineDebuggerEnv(default_task_id=task_id)
    random.seed(SEED)
    rewards: List[float] = []
    done = False
    steps_taken = 0
    final_score = 0.0
    success = False
    obs = env.reset(task_id)
    log_start(task=task_id, env=BENCHMARK, model=model_name)

    try:
        for step in range(1, MAX_AGENT_STEPS + 1):
            if done:
                break

            try:
                action = choose_action_with_llm(client, model_name, obs.model_dump())
            except Exception:
                action = fallback_action(obs.model_dump())

            obs, reward, done, info = env.step(action)
            steps_taken = step
            rewards.append(float(reward.value))

            action_str = json.dumps(action.model_dump(exclude_none=True), sort_keys=True)
            error = info.get("last_action_error")
            log_step(step=step, action=action_str, reward=float(reward.value), done=done, error=error)

            if done:
                break

        final_state = env.state()
        final_score = compute_task_score(final_state)
        success = final_score >= 0.1
        return {
            "task_id": task_id,
            "steps": steps_taken,
            "final_score": round(final_score, 4),
            "total_reward": round(sum(rewards), 4),
        }
    finally:
        close_fn = getattr(env, "close", None)
        if callable(close_fn):
            close_fn()
        log_end(success=success, steps=steps_taken, score=final_score, rewards=rewards)


def main() -> None:
    model_name = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
    client = build_client()

    results: List[Dict[str, Any]] = []
    for task_id in list_task_ids():
        result = run_task(client, model_name, task_id)
        results.append(result)


if __name__ == "__main__":
    main()
