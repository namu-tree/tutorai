from __future__ import annotations

from agents.critic import CriticAgent
from agents.curriculum import CurriculumAgent
from agents.designer import ProblemDesignerAgent
from agents.final_editor import FinalEditorAgent
from agents.solver import SolverAgent
from agents.student_model import StudentModelAgent
from core.curriculum_scope import get_scope
from core.models import CurriculumReport, GenerationResponse, TaskSpec
from core.rules import DecisionRules


def _safe_dump(obj):
    if obj is None:
        return "None"
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)


class Orchestrator:
    def __init__(self) -> None:
        self.curriculum_agent = CurriculumAgent()
        self.designer_agent = ProblemDesignerAgent()
        self.solver_agent = SolverAgent()
        self.critic_agent = CriticAgent()
        self.student_model_agent = StudentModelAgent()
        self.final_editor_agent = FinalEditorAgent()

    def generate(self, task_spec: TaskSpec) -> GenerationResponse:
        revision_history: list[dict[str, str]] = []

        curriculum = None
        draft = None
        last_solver = None
        last_critic = None
        last_student = None

        try:
            curriculum = self.curriculum_agent.run(task_spec)
            official = get_scope(task_spec.grade, task_spec.unit)
            if official:
                allowed = list(dict.fromkeys((official.get("allowed_concepts") or []) + curriculum.allowed_concepts))
                forbidden = list(dict.fromkeys((official.get("forbidden_concepts") or []) + curriculum.forbidden_concepts))
                curriculum = CurriculumReport(
                    message_type=curriculum.message_type,
                    request_id=curriculum.request_id,
                    curriculum_fit=curriculum.curriculum_fit,
                    allowed_concepts=allowed or curriculum.allowed_concepts,
                    forbidden_concepts=forbidden or curriculum.forbidden_concepts,
                    prerequisites=curriculum.prerequisites,
                    recommended_item_patterns=curriculum.recommended_item_patterns,
                    curriculum_notes=curriculum.curriculum_notes,
                )
            print("=== CURRICULUM ===")
            print(_safe_dump(curriculum))
        except Exception as e:
            return GenerationResponse(
                status="rejected",
                request_id=task_spec.request_id,
                curriculum=curriculum,
                last_solver_report=last_solver,
                last_critic_report=last_critic,
                last_student_report=last_student,
                message=f"CurriculumAgent 실패: {e}",
            )

        if curriculum.curriculum_fit != "pass":
            return GenerationResponse(
                status="rejected",
                request_id=task_spec.request_id,
                curriculum=curriculum,
                last_solver_report=last_solver,
                last_critic_report=last_critic,
                last_student_report=last_student,
                message="교육과정 적합성 검토 실패",
            )

        for round_idx in range(1, task_spec.constraints.max_revision_rounds + 1):
            try:
                draft = self.designer_agent.run(
                    {
                        "task_spec": task_spec,
                        "curriculum": curriculum,
                        "draft_version": round_idx,
                    }
                )
                print("=== DRAFT ===")
                print(_safe_dump(draft))
            except Exception as e:
                return GenerationResponse(
                    status="rejected",
                    request_id=task_spec.request_id,
                    curriculum=curriculum,
                    last_solver_report=last_solver,
                    last_critic_report=last_critic,
                    last_student_report=last_student,
                    message=f"ProblemDesignerAgent 실패: {e}",
                )

            try:
                last_solver = self.solver_agent.run(draft)
                print("=== SOLVER ===")
                print(_safe_dump(last_solver))
            except Exception as e:
                return GenerationResponse(
                    status="rejected",
                    request_id=task_spec.request_id,
                    curriculum=curriculum,
                    last_solver_report=last_solver,
                    last_critic_report=last_critic,
                    last_student_report=last_student,
                    message=f"SolverAgent 실패: {e}",
                )

            try:
                last_critic = self.critic_agent.run(
                    {
                        "draft": draft,
                        "solver": last_solver,
                        "curriculum": curriculum,
                    }
                )
                print("=== CRITIC ===")
                print(_safe_dump(last_critic))
            except Exception as e:
                return GenerationResponse(
                    status="rejected",
                    request_id=task_spec.request_id,
                    curriculum=curriculum,
                    last_solver_report=last_solver,
                    last_critic_report=last_critic,
                    last_student_report=last_student,
                    message=f"CriticAgent 실패: {e}",
                )

            try:
                last_student = None
                if task_spec.student_profile is not None:
                    last_student = self.student_model_agent.run(
                        {
                            "draft": draft,
                            "solver": last_solver,
                            "student_profile": task_spec.student_profile,
                        }
                    )
                    print("=== STUDENT ===")
                    print(_safe_dump(last_student))
            except Exception as e:
                return GenerationResponse(
                    status="rejected",
                    request_id=task_spec.request_id,
                    curriculum=curriculum,
                    last_solver_report=last_solver,
                    last_critic_report=last_critic,
                    last_student_report=last_student,
                    message=f"StudentModelAgent 실패: {e}",
                )

            try:
                decision = DecisionRules.decide(
                    task_spec=task_spec,
                    solver=last_solver,
                    critic=last_critic,
                    student=last_student,
                    round_idx=round_idx,
                )
            except Exception as e:
                return GenerationResponse(
                    status="rejected",
                    request_id=task_spec.request_id,
                    curriculum=curriculum,
                    last_solver_report=last_solver,
                    last_critic_report=last_critic,
                    last_student_report=last_student,
                    message=f"DecisionRules 실패: {e}",
                )

            if decision.status == "approved":
                revision_history.append({"version": str(round_idx), "status": "approved"})
                try:
                    final_problem = self.final_editor_agent.run(
                        {
                            "draft": draft,
                            "revision_history": revision_history,
                            "student_check": "pass" if last_student else "not_run",
                        }
                    )
                except Exception as e:
                    return GenerationResponse(
                        status="rejected",
                        request_id=task_spec.request_id,
                        curriculum=curriculum,
                        last_solver_report=last_solver,
                        last_critic_report=last_critic,
                        last_student_report=last_student,
                        message=f"FinalEditorAgent 실패: {e}",
                    )

                return GenerationResponse(
                    status="approved",
                    request_id=task_spec.request_id,
                    curriculum=curriculum,
                    final_problem=final_problem,
                    last_solver_report=last_solver,
                    last_critic_report=last_critic,
                    last_student_report=last_student,
                    message="문항 생성 및 검증 완료",
                )

            if decision.status == "rejected":
                revision_history.append(
                    {"version": str(round_idx), "status": "rejected", "reason": decision.reason}
                )
                return GenerationResponse(
                    status="rejected",
                    request_id=task_spec.request_id,
                    curriculum=curriculum,
                    last_solver_report=last_solver,
                    last_critic_report=last_critic,
                    last_student_report=last_student,
                    message=decision.reason,
                )

            revision_history.append(
                {"version": str(round_idx), "status": "revised", "reason": decision.reason}
            )

            if decision.revision_request:
                task_spec.revision_feedback.extend(decision.revision_request.must_fix)
                task_spec.revision_feedback.extend(decision.revision_request.should_fix)

        return GenerationResponse(
            status="rejected",
            request_id=task_spec.request_id,
            curriculum=curriculum,
            last_solver_report=last_solver,
            last_critic_report=last_critic,
            last_student_report=last_student,
            message="최대 수정 횟수를 초과하여 반려됨",
        )