from __future__ import annotations

from typing import Dict

from agents.base import BaseAgent
from core.models import ProblemDraft, SolverReport, StudentAlignmentReport, TargetedWeaknessCoverage


class StudentModelAgent(BaseAgent[Dict, StudentAlignmentReport]):
    name = "StudentModelAgent"

    def run(self, payload: Dict) -> StudentAlignmentReport:
        draft: ProblemDraft = payload["draft"]
        _solver: SolverReport = payload["solver"]
        profile = payload.get("student_profile")

        weaknesses = profile.target_weakness if profile else []
        draft_concepts = set(draft.target_concepts)

        coverage_items: list[TargetedWeaknessCoverage] = []
        for weakness in weaknesses:
            coverage = 0.85 if weakness in draft_concepts else 0.55
            coverage_items.append(
                TargetedWeaknessCoverage(node=weakness, coverage=coverage)
            )

        if coverage_items:
            alignment_score = sum(item.coverage for item in coverage_items) / len(coverage_items)
        else:
            alignment_score = 0.7

        comments = []
        if weaknesses:
            comments.append("학생 약점과의 정렬도를 draft 기준으로 계산함")
        else:
            comments.append("student_profile이 없어 일반 진단값으로 계산함")

        return StudentAlignmentReport(
            request_id=draft.request_id,
            draft_version=draft.draft_version,
            alignment_score=alignment_score,
            diagnostic_value=0.8,
            targeted_weakness_coverage=coverage_items,
            expected_error_patterns=[
                "판별식 부호 조건을 잘못 해석하는 오류",
                "교점 개수와 그래프 위치 관계를 혼동하는 오류",
            ],
            comments=comments,
        )