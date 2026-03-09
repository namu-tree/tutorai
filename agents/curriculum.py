from __future__ import annotations

from agents.base import BaseAgent
from core.models import CurriculumReport, TaskSpec
from services.llm import LLMClient

CURRICULUM_SYSTEM_PROMPT = """
# Role
당신은 한국 중1~고2 수학 교육과정을 검토하는 교육과정 분석 에이전트다.

# Objective
주어진 학년, 학기, 단원, 토픽이 교육과정상 어떤 개념을 허용하는지 판단하고,
선수 개념과 금지 개념을 명시한다.

# Rules
1. 교육과정 범위를 벗어나는 개념은 forbidden_concepts에 넣는다.
2. 실제 문제 생성을 하지 않는다.
3. 출력은 curriculum_report JSON만 작성한다.
"""


class CurriculumAgent(BaseAgent[TaskSpec, CurriculumReport]):
    name = "CurriculumAgent"

    def __init__(self) -> None:
        self.llm = LLMClient()

    def run(self, payload: TaskSpec) -> CurriculumReport:
        return self.llm.structured_generate(
            system_prompt=CURRICULUM_SYSTEM_PROMPT,
            user_payload=payload.model_dump(),
            response_model=CurriculumReport,
        )