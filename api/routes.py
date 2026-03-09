from __future__ import annotations

from fastapi import APIRouter
from core.models import GenerationResponse, TaskSpec
from core.orchestrator import Orchestrator

router = APIRouter(prefix="/api")
orchestrator = Orchestrator()


@router.post("/generate-problem", response_model=GenerationResponse)
def generate_problem(task_spec: TaskSpec) -> GenerationResponse:
    return orchestrator.generate(task_spec)