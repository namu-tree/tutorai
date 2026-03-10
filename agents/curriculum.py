from __future__ import annotations

from agents.base import BaseAgent
from core.curriculum_scope import get_scope_for_prompt
from core.models import CurriculumReport, TaskSpec
from services.llm import LLMClient

CURRICULUM_SYSTEM_PROMPT = """
# Role
당신은 한국 중학교 1학년부터 고등학교 3학년까지의 수학 교육과정을 검토하는 교육과정 분석 에이전트다.

# Objective
주어진 학년(중1~고3), 학기, 교과(예: 수학, 수학Ⅰ, 수학Ⅱ, 확률과 통계, 미적분 등), 단원, 토픽이
공식 교육과정 범위 안에서 어떤 개념을 허용하는지 판단하고,
선수 개념과 금지 개념을 명시한다.

# Rules
1. user_payload에 official_scope가 있으면, 그 내용을 최우선으로 따른다. 허용·금지 개념을 그 범위에 맞춘다.
2. 주어진 학년·과정에서 아직 배우지 않은 상위 개념(예: 미적분, 복소수, 행렬 등)은 forbidden_concepts에 넣는다.
3. 교육과정 범위를 벗어난 대학 수준/올림피아드 수준 개념도 forbidden_concepts에 넣는다.
4. 실제 문제 생성을 하지 않는다.
5. 출력은 curriculum_report JSON만 작성한다.
"""


class CurriculumAgent(BaseAgent[TaskSpec, CurriculumReport]):
    name = "CurriculumAgent"

    def __init__(self) -> None:
        self.llm = LLMClient()

    def run(self, payload: TaskSpec) -> CurriculumReport:
        user = payload.model_dump()
        official = get_scope_for_prompt(payload.grade, payload.unit)
        if official:
            user["official_scope"] = official
        return self.llm.structured_generate(
            system_prompt=CURRICULUM_SYSTEM_PROMPT,
            user_payload=user,
            response_model=CurriculumReport,
        )