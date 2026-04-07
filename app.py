from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from openenv_datapipeline.env import DataPipelineDebuggerEnv
from openenv_datapipeline.models import PipelineAction
from openenv_datapipeline.tasks import TASKS

app = FastAPI(title="OpenEnv Data Pipeline Debugger", version="1.0.0")
env = DataPipelineDebuggerEnv()


class ResetRequest(BaseModel):
    task_id: str | None = None


@app.get("/")
def index() -> dict:
    return {
        "name": "data-pipeline-debugger-openenv",
        "status": "ok",
        "tasks": list(TASKS.keys()),
        "endpoints": ["/reset", "/step", "/state"],
    }


@app.post("/reset")
def reset(request: ResetRequest) -> dict:
    try:
        obs = env.reset(request.task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"observation": obs.model_dump()}


@app.post("/step")
def step(action: PipelineAction) -> dict:
    observation, reward, done, info = env.step(action)
    return {
        "observation": observation.model_dump(),
        "reward": reward.model_dump(),
        "done": done,
        "info": info,
    }


@app.get("/state")
def state() -> dict:
    return {"state": env.state().model_dump()}
