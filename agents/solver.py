from __future__ import annotations

from agents.base import BaseAgent
from core.models import ProblemDraft, SolverReport, UniquenessCheck


class SolverAgent(BaseAgent[ProblemDraft, SolverReport]):
    name = "SolverAgent"

    def run(self, payload: ProblemDraft) -> SolverReport:
        # 현재 단계에서는 designer가 만든 draft를 기준으로 일관성만 유지한다.
        # 추후 sympy 기반 검증기로 교체 예정.
        solution_summary = payload.intended_solution_path or []

        derived_answer = payload.intended_answer or ""

        ambiguity_flags: list[str] = []
        mathematical_issues: list[str] = []

        if not payload.question.strip():
            ambiguity_flags.append("문제 지문이 비어 있음")

        if len(payload.options) != 5:
            ambiguity_flags.append("선택지 수가 5개가 아님")

        is_unique = True
        uniqueness_reason = "현재 버전에서는 designer가 생성한 정답을 기준으로 일관성 검사를 수행함"

        if not derived_answer:
            is_unique = False
            uniqueness_reason = "의도한 정답이 비어 있어 유일성 검사를 완료할 수 없음"

        return SolverReport(
            request_id=payload.request_id,
            draft_version=payload.draft_version,
            solve_status="pass" if is_unique else "fail",
            derived_answer=derived_answer,
            solution_summary=solution_summary,
            alternative_paths=[],
            uniqueness_check=UniquenessCheck(
                is_unique=is_unique,
                reason=uniqueness_reason,
            ),
            ambiguity_flags=ambiguity_flags,
            mathematical_issues=mathematical_issues,
        )