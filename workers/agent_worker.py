from __future__ import annotations

import pathlib
import sys

PROJECT_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import asyncio
import json
import os
from typing import Any, Dict

from agents.critic import CriticAgent
from agents.curriculum import CurriculumAgent
from agents.designer import ProblemDesignerAgent
from agents.final_editor import FinalEditorAgent
from agents.solver import SolverAgent
from agents.student_model import StudentModelAgent
from core.models import (
    AgentCommand,
    AgentResult,
    CurriculumReport,
    ProblemDraft,
    SolverReport,
    StudentProfile,
    TaskSpec,
)
from services.bus import BusConfig, RedisBus


class AgentRegistry:
    def __init__(self) -> None:
        self._agents = {
            "CurriculumAgent": CurriculumAgent(),
            "ProblemDesignerAgent": ProblemDesignerAgent(),
            "SolverAgent": SolverAgent(),
            "CriticAgent": CriticAgent(),
            "StudentModelAgent": StudentModelAgent(),
            "FinalEditorAgent": FinalEditorAgent(),
        }

    def _adapt_payload(self, agent_name: str, payload: Dict[str, Any]) -> Any:
        if agent_name == "CurriculumAgent":
            return TaskSpec.model_validate(payload)

        if agent_name == "ProblemDesignerAgent":
            return {
                "task_spec": TaskSpec.model_validate(payload["task_spec"]),
                "curriculum": CurriculumReport.model_validate(payload["curriculum"]),
                "draft_version": int(payload.get("draft_version", 1)),
            }

        if agent_name == "SolverAgent":
            return ProblemDraft.model_validate(payload)

        if agent_name == "CriticAgent":
            return {
                "draft": ProblemDraft.model_validate(payload["draft"]),
                "solver": SolverReport.model_validate(payload["solver"]),
                "curriculum": CurriculumReport.model_validate(payload["curriculum"]),
            }

        if agent_name == "StudentModelAgent":
            student_profile = payload.get("student_profile")
            return {
                "draft": ProblemDraft.model_validate(payload["draft"]),
                "solver": SolverReport.model_validate(payload["solver"]),
                "student_profile": StudentProfile.model_validate(student_profile)
                if isinstance(student_profile, dict)
                else student_profile,
            }

        if agent_name == "FinalEditorAgent":
            return {
                "draft": ProblemDraft.model_validate(payload["draft"]),
                "revision_history": payload.get("revision_history", []),
                "student_check": payload.get("student_check", "not_run"),
            }

        return payload

    def run(self, agent_name: str, payload: Dict[str, Any]) -> Any:
        if agent_name not in self._agents:
            raise ValueError(f"Unknown agent_name: {agent_name}")
        adapted = self._adapt_payload(agent_name, payload)
        return self._agents[agent_name].run(adapted)


async def main() -> None:
    cfg = BusConfig.from_env()
    bus = RedisBus(cfg)
    registry = AgentRegistry()

    # Streams + consumer group
    stream_key = cfg.stream_agent_commands()
    group = os.getenv("AGENT_COMMANDS_GROUP", "agent_workers")
    consumer = os.getenv("AGENT_COMMANDS_CONSUMER", "agent_worker_1")

    r = bus._redis  # internal redis client
    try:
        await r.xgroup_create(stream_key, group, id="0-0", mkstream=True)
    except Exception:
        # group may already exist
        pass

    last_id = ">"
    while True:
        resp = await r.xreadgroup(group, consumer, {stream_key: last_id}, count=10, block=5000)
        if not resp:
            continue
        _, entries = resp[0]
        for entry_id, fields in entries:
            raw = fields.get("command")
            if not raw:
                await r.xack(stream_key, group, entry_id)
                continue
            try:
                cmd = AgentCommand.model_validate_json(raw)
            except Exception:
                cmd = AgentCommand.model_validate(json.loads(raw))

            try:
                output = registry.run(cmd.agent_name, cmd.payload)
                result = AgentResult(
                    command_id=cmd.command_id,
                    session_id=cmd.session_id,
                    agent_name=cmd.agent_name,
                    ok=True,
                    result=output.model_dump() if hasattr(output, "model_dump") else {"value": output},
                )
            except Exception as e:
                result = AgentResult(
                    command_id=cmd.command_id,
                    session_id=cmd.session_id,
                    agent_name=cmd.agent_name,
                    ok=False,
                    result={},
                    error=str(e),
                )

            await bus.enqueue_agent_result(result)
            await r.xack(stream_key, group, entry_id)


if __name__ == "__main__":
    asyncio.run(main())

