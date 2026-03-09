from __future__ import annotations

from typing import Dict

from agents.base import BaseAgent
from core.models import CriticReport, CurriculumReport, ProblemDraft, SolverReport


class CriticAgent(BaseAgent[Dict, CriticReport]):
    name = "CriticAgent"

    def run(self, payload: Dict) -> CriticReport:
        draft: ProblemDraft = payload["draft"]
        solver: SolverReport = payload["solver"]
        curriculum: CurriculumReport = payload["curriculum"]

        fatal_issues: list[str] = []
        major_issues: list[str] = []
        minor_issues: list[str] = []
        revision_requests: list[str] = []

        if not draft.question.strip():
            fatal_issues.append("문제 지문이 비어 있음")

        if len(draft.options) != 5:
            fatal_issues.append("선택지 수가 5개가 아님")

        if not draft.intended_answer:
            fatal_issues.append("의도한 정답이 비어 있음")

        if not solver.uniqueness_check.is_unique:
            fatal_issues.append("정답 유일성 검증 실패")

        if curriculum.curriculum_fit != "pass":
            fatal_issues.append("교육과정 적합성 실패")

        if not draft.intended_solution_path:
            major_issues.append("풀이 과정이 비어 있음")
            revision_requests.append("intended_solution_path를 단계별로 포함하라")

        if not draft.target_concepts:
            major_issues.append("target_concepts가 비어 있음")
            revision_requests.append("문항이 겨냥하는 핵심 개념 태그를 포함하라")

        if fatal_issues:
            review_decision = "reject"
        elif major_issues:
            review_decision = "revise"
        else:
            review_decision = "pass"
            minor_issues.append("기본 구조는 양호하나 실제 서비스에서는 수학적 자동 검증기 추가 권장")

        clarity_score = 0.9 if draft.question.strip() else 0.2
        curriculum_fit_score = 0.95 if curriculum.curriculum_fit == "pass" else 0.3
        difficulty_fit_score = 0.8 if (draft.metadata.get("difficulty") or draft.metadata.get("difficulty_target")) else 0.5
        distractor_quality_score = 0.8 if len(draft.options) == 5 else 0.2

        return CriticReport(
            request_id=draft.request_id,
            draft_version=draft.draft_version,
            review_decision=review_decision,
            fatal_issues=fatal_issues,
            major_issues=major_issues,
            minor_issues=minor_issues,
            clarity_score=clarity_score,
            curriculum_fit_score=curriculum_fit_score,
            difficulty_fit_score=difficulty_fit_score,
            distractor_quality_score=distractor_quality_score,
            revision_requests=revision_requests,
        )