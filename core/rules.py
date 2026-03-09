from __future__ import annotations

from typing import Optional
from core.models import (
    AgentDecision,
    CriticReport,
    OrchestratorDecision,
    RevisionRequest,
    SolverReport,
    StudentAlignmentReport,
    TaskSpec,
)


class DecisionRules:
    @staticmethod
    def decide(
        *,
        task_spec: TaskSpec,
        solver: SolverReport,
        critic: CriticReport,
        student: Optional[StudentAlignmentReport],
        round_idx: int,
    ) -> OrchestratorDecision:
        if not solver.uniqueness_check.is_unique:
            return OrchestratorDecision(
                status=AgentDecision.REVISE,
                reason="정답 유일성 실패",
                revision_request=RevisionRequest(
                    request_id=task_spec.request_id,
                    draft_version=round_idx,
                    revision_version=round_idx + 1,
                    must_fix=[solver.uniqueness_check.reason],
                    should_fix=[],
                    keep_unchanged=[
                        task_spec.grade,
                        task_spec.unit,
                        task_spec.topic,
                        task_spec.difficulty_target.value,
                    ],
                ),
            )

        if critic.fatal_issues:
            status = AgentDecision.REJECTED if round_idx >= task_spec.constraints.max_revision_rounds else AgentDecision.REVISE
            return OrchestratorDecision(
                status=status,
                reason="Critic이 치명적 결함을 탐지함",
                revision_request=RevisionRequest(
                    request_id=task_spec.request_id,
                    draft_version=round_idx,
                    revision_version=round_idx + 1,
                    must_fix=critic.fatal_issues,
                    should_fix=critic.major_issues,
                    keep_unchanged=[
                        task_spec.grade,
                        task_spec.unit,
                        task_spec.topic,
                        task_spec.difficulty_target.value,
                    ],
                ) if status == AgentDecision.REVISE else None,
            )

        if student and task_spec.purpose.value == "diagnostic" and student.alignment_score < 0.60:
            return OrchestratorDecision(
                status=AgentDecision.REVISE,
                reason="진단형 문항으로서 약점 정렬도가 부족함",
                revision_request=RevisionRequest(
                    request_id=task_spec.request_id,
                    draft_version=round_idx,
                    revision_version=round_idx + 1,
                    must_fix=["학생 약점과 더 직접적으로 연결되는 문항으로 수정"],
                    should_fix=[],
                    keep_unchanged=[task_spec.unit, task_spec.topic],
                ),
            )

        return OrchestratorDecision(
            status=AgentDecision.APPROVED,
            reason="모든 핵심 검증을 통과함",
            revision_request=None,
        )