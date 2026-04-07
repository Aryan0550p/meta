# Data Pipeline Debugger OpenEnv

A real-world OpenEnv environment for training and evaluating AI agents on ETL incident debugging.

## Why this environment matters

Data teams spend significant engineering time diagnosing schema drift, null propagation, and aggregation regressions in production pipelines. This environment models that workflow with deterministic bug catalogs, staged diagnosis actions, and progress-sensitive rewards.

## OpenEnv interface

The environment implements:

- `reset(task_id)` -> returns initial typed observation
- `step(action)` -> returns `(observation, reward, done, info)`
- `state()` -> returns current typed state snapshot

Typed Pydantic models:

- Observation: `PipelineObservation`
- Action: `PipelineAction`
- Reward: `PipelineReward`

## Action space

`PipelineAction` includes:

- `action_type`: one of `inspect_stage`, `run_validation`, `explain_bug`, `apply_fix`, `finish`
- Optional fields by action type: `stage`, `rule`, `bug_id`, `explanation`

## Observation space

`PipelineObservation` includes:

- Task context: `task_id`, `objective`
- Episode progress: `step_count`, `max_steps`, `latest_event`
- Tooling choices: `visible_stages`, `visible_rules`
- Bug tracking list: discovered/explained/fixed flags per bug
- `running_score_hint` in [0.0, 1.0]

## Tasks and graders

Three deterministic tasks with increasing difficulty:

1. easy_schema_mismatch (easy)
2. medium_null_and_cast (medium)
3. hard_multibug_regression (hard)

Grader properties:

- Score in [0.0, 1.0]
- Deterministic
- Weighted objective quality: discovery (20%), explanation (30%), fix quality (50%)
- Penalizes invalid/repeated actions

## Reward shaping

Per-step reward components:

- Positive: discovery (+0.10), valid explanation (+0.18), successful fix (+0.24), completion bonus (+0.08)
- Negative: invalid action (-0.08), repeated action (-0.03), per-step cost (-0.01)
- Clamped to [0.0, 1.0]

This creates dense trajectory signals and discourages infinite loops.

## Project structure

- `openenv_datapipeline/models.py` typed models
- `openenv_datapipeline/tasks.py` task definitions
- `openenv_datapipeline/graders.py` grader and reward helpers
- `openenv_datapipeline/env.py` OpenEnv environment logic
- `app.py` FastAPI service endpoints (`/reset`, `/step`, `/state`)
- `openenv.yaml` environment metadata
- `inference.py` baseline model runner

## Local setup

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run API locally:

```bash
uvicorn app:app --host 0.0.0.0 --port 7860
```

## Docker

```bash
docker build -t data-pipeline-debugger .
docker run -p 7860:7860 data-pipeline-debugger
```

## Baseline inference

Required environment variables:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`
- `OPENAI_API_KEY` (optional fallback if `HF_TOKEN` is not set)

Run baseline:

```bash
python inference.py
```

Logs are emitted in structured format using `[START]`, `[STEP]`, and `[END]` lines.

## Baseline benchmark (reproducible)

With deterministic fallback mode (unreachable API base URL) and `SEED=42`:

- easy_schema_mismatch: score 1.0000 (3 steps)
- medium_null_and_cast: score 1.0000 (5 steps)
- hard_multibug_regression: score 1.0000 (9 steps)
- average_score: 1.0000

Run command used:

```bash
OPENAI_API_KEY=dummy API_BASE_URL=http://127.0.0.1:9/v1 MODEL_NAME=gpt-4o-mini python inference.py
```

## Hugging Face Spaces deployment notes

- Use Docker SDK Space
- Ensure Space has `openenv` tag
- Expose service on port `7860`
- Health check root endpoint: `GET /`
- Reset endpoint for validators: `POST /reset`
