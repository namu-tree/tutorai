from __future__ import annotations

from typing import Dict
from agents.base import BaseAgent
from core.curriculum_scope import get_scope_for_prompt
from core.models import CurriculumReport, ProblemDraft, TaskSpec
from services.llm import LLMClient

DESIGNER_SYSTEM_PROMPT = """
# Role
당신은 한국 중학교 1학년부터 고등학교 3학년까지의 교육과정을 기반으로
수학 문항을 설계하는 전문 출제 에이전트다.

# Objective
주어진 task_spec과 curriculum_report를 바탕으로
해당 학년·과정(중등/고등), 단원, 토픽, 난이도, 목적(연습/진단/시험)에 맞는 문항 초안을 작성한다.

# Rules
1. user_payload에 official_scope가 있으면 반드시 준수한다. 허용된 개념 범위 안에서만 출제하고, 금지 개념은 사용하지 않는다. (예: 고1 곱셈공식이면 삼차 공식 (a+b)^3, a^3±b^3 등을 반드시 포함할 수 있는 문항을 낸다. 중3 수준만 내면 안 된다.)
2. 반드시 LaTeX를 사용한다.
3. 정답이 유일하도록 의도하여 설계한다.
4. 중등(중1~중3) 수준에서는 고등 과정(미적분, 복소수, 행렬 등)의 개념을 사용하지 않는다.
5. 고등 과정에서는 해당 과목의 범위 안에서만 개념을 사용하고, 대학 수준의 심화 개념은 사용하지 않는다.
6. 출력은 problem_draft JSON만 작성한다.
"""


class ProblemDesignerAgent(BaseAgent[Dict, ProblemDraft]):
    name = "ProblemDesignerAgent"

    def __init__(self) -> None:
        self.llm = LLMClient()

    def run(self, payload: Dict) -> ProblemDraft:
        task: TaskSpec = payload["task_spec"]
        curriculum: CurriculumReport = payload["curriculum"]
        version: int = payload["draft_version"]
        user = {
            "task_spec": task.model_dump(),
            "curriculum_report": curriculum.model_dump(),
            "draft_version": version,
        }
        official = get_scope_for_prompt(task.grade, task.unit)
        if official:
            user["official_scope"] = official
        return self.llm.structured_generate(
            system_prompt=DESIGNER_SYSTEM_PROMPT,
            user_payload=user,
            response_model=ProblemDraft,
        )