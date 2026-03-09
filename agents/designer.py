from __future__ import annotations

from typing import Dict
from agents.base import BaseAgent
from core.models import CurriculumReport, ProblemDraft, TaskSpec
from services.llm import LLMClient

DESIGNER_SYSTEM_PROMPT = """
# Role
당신은 수학 문항을 설계하는 전문 출제 에이전트다.

# Objective
주어진 task_spec과 curriculum_report를 바탕으로 목표 난이도와 목적에 맞는 문항 초안을 작성한다.

# Rules
1. 반드시 LaTeX를 사용한다.
2. 정답이 유일하도록 의도하여 설계한다.
3. 출력은 problem_draft JSON만 작성한다.
"""


class ProblemDesignerAgent(BaseAgent[Dict, ProblemDraft]):
    name = "ProblemDesignerAgent"

    def __init__(self) -> None:
        self.llm = LLMClient()

    def run(self, payload: Dict) -> ProblemDraft:
        task: TaskSpec = payload["task_spec"]
        curriculum: CurriculumReport = payload["curriculum"]
        version: int = payload["draft_version"]

        return self.llm.structured_generate(
            system_prompt=DESIGNER_SYSTEM_PROMPT,
            user_payload={
                "task_spec": task.model_dump(),
                "curriculum_report": curriculum.model_dump(),
                "draft_version": version,
            },
            response_model=ProblemDraft,
        )