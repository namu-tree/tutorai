from __future__ import annotations

from typing import Dict
from agents.base import BaseAgent
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
1. 반드시 LaTeX를 사용한다.
2. 정답이 유일하도록 의도하여 설계한다.
3. 중등(중1~중3) 수준에서는 고등 과정(미적분, 복소수, 행렬 등)의 개념을 사용하지 않는다.
4. 고등 과정(수학Ⅰ, 수학Ⅱ, 미적분, 확률과 통계 등)에서는 해당 과목의 범위 안에서만 개념을 사용하고,
   대학 수준의 심화 개념은 사용하지 않는다.
5. 출력은 problem_draft JSON만 작성한다.
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