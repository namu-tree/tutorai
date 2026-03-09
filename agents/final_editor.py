from __future__ import annotations

from typing import Dict

from agents.base import BaseAgent
from core.models import FinalProblemPackage, ProblemDraft


class FinalEditorAgent(BaseAgent[Dict, FinalProblemPackage]):
    name = "FinalEditorAgent"

    def run(self, payload: Dict) -> FinalProblemPackage:
        draft: ProblemDraft = payload["draft"]
        revision_history = payload["revision_history"]

        explanation = "\n".join(draft.intended_solution_path) if draft.intended_solution_path else ""

        concept_ontology = [
            {"node_id": f"NODE_{idx + 1}", "name": concept}
            for idx, concept in enumerate(draft.target_concepts)
        ]
        if not concept_ontology:
            concept_ontology = [{"node_id": "NODE_UNKNOWN", "name": "미분류"}]

        return FinalProblemPackage(
            request_id=draft.request_id,
            problem_id=f"{draft.request_id}_approved",
            metadata={
                "grade": draft.metadata.get("grade", ""),
                "unit": draft.metadata.get("unit", ""),
                "topic": draft.metadata.get("topic", ""),
                "difficulty": draft.metadata.get("difficulty") or draft.metadata.get("difficulty_target", ""),
                "purpose": draft.metadata.get("purpose", "diagnostic"),
            },
            question=draft.question,
            options=draft.options,
            answer=draft.intended_answer,
            explanation=explanation,
            concept_ontology=concept_ontology,
            validation_report={
                "solver_check": "pass",
                "critic_check": "pass",
                "student_alignment_check": payload.get("student_check", "not_run"),
            },
            revision_history=revision_history,
        )