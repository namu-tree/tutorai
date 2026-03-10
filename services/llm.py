from __future__ import annotations

import json
import os
from typing import Any, Dict, Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

T = TypeVar("T", bound=BaseModel)


def _to_str_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.append(item.strip())
            elif isinstance(item, dict):
                # 자주 나오는 키 우선
                for key in [
                    "name",
                    "concept",
                    "title",
                    "label",
                    "description",
                    "text",
                    "value",
                ]:
                    if key in item and item[key]:
                        result.append(str(item[key]).strip())
                        break
                else:
                    result.append(json.dumps(item, ensure_ascii=False))
            else:
                result.append(str(item).strip())
        return result

    if isinstance(value, dict):
        # {"1": "...", "2": "..."} 같은 선택지 dict 대응
        return _to_str_list(list(value.values()))

    return [str(value).strip()]


def _unwrap_known_keys(data: dict[str, Any]) -> dict[str, Any]:
    for key in [
        "curriculum_report",
        "problem_draft",
        "solver_report",
        "critic_report",
        "student_alignment_report",
        "final_problem_package",
        "draft",
        "item",
    ]:
        if key in data and isinstance(data[key], dict):
            return data[key]
    return data


def _normalize_metadata(meta: Any) -> dict[str, str]:
    if not isinstance(meta, dict):
        return {}

    result: dict[str, str] = {}
    for k, v in meta.items():
        if isinstance(v, str):
            result[k] = v
        else:
            result[k] = json.dumps(v, ensure_ascii=False)
    return result


def _normalize_for_model(data: dict[str, Any], model_name: str) -> dict[str, Any]:
    data = _unwrap_known_keys(data)

    if model_name == "CurriculumReport":
        scope = data.get("scope") if isinstance(data.get("scope"), dict) else {}
        analysis = data.get("analysis") if isinstance(data.get("analysis"), dict) else {}

        prerequisites = (
            data.get("prerequisites")
            or data.get("prerequisite_concepts")
            or analysis.get("prerequisite_concepts")
            or scope.get("prerequisite_concepts")
            or scope.get("prerequisites")
            or data.get("required_concepts")
            or []
        )

        curriculum_notes = (
            data.get("curriculum_notes")
            or data.get("notes_on_scope")
            or scope.get("notes_on_scope")
            or data.get("notes_on_edge_cases")
            or data.get("notes")
            or analysis.get("notes")
            or []
        )

        recommended_item_patterns = (
            data.get("recommended_item_patterns")
            or data.get("recommended_focus")
            or data.get("diagnostic_focus")
            or data.get("difficulty_guidance_level_2")
            or []
        )

        allowed = (
            data.get("allowed_concepts")
            or analysis.get("in_scope_concepts")
            or analysis.get("allowed_concepts")
            or scope.get("allowed_concepts")
        )
        forbidden = (
            data.get("forbidden_concepts")
            or analysis.get("forbidden_concepts")
            or scope.get("forbidden_concepts")
        )

        return {
            "message_type": "curriculum_report",
            "request_id": data.get("request_id", ""),
            "curriculum_fit": data.get("curriculum_fit", "pass"),
            "allowed_concepts": _to_str_list(allowed),
            "forbidden_concepts": _to_str_list(forbidden),
            "prerequisites": _to_str_list(prerequisites),
            "recommended_item_patterns": _to_str_list(recommended_item_patterns),
            "curriculum_notes": _to_str_list(curriculum_notes),
        }

    if model_name == "ProblemDraft":
        problem_block = data.get("problem") or data
        solution_block = data.get("solution", {})
        diagnostic_block = data.get("diagnostic", {})

        # items: [ { stem, options/choices, answer/answer_key } ] 형태 처리
        if isinstance(data.get("items"), list) and len(data["items"]) > 0:
            first = data["items"][0]
            if isinstance(first, dict):
                problem_block = first

        if isinstance(problem_block, dict):
            question = (
                problem_block.get("stem")
                or problem_block.get("question")
                or data.get("stem")
                or ""
            )
            raw_options = (
                problem_block.get("options")
                or problem_block.get("choices")
                or data.get("options")
                or data.get("choices")
                or []
            )
            intended_answer = (
                problem_block.get("answer_key")
                or problem_block.get("answer")
                or problem_block.get("correct_answer")
                or problem_block.get("correct_choice")
                or data.get("answer_key")
                or data.get("answer")
                or data.get("correct_answer")
                or data.get("correct_choice")
                or data.get("answer_index")
                or ""
            )
            if not intended_answer:
                idx = problem_block.get("correct_choice_index") or data.get("correct_choice_index")
                if idx is not None:
                    try:
                        i = int(idx)
                        if 1 <= i <= 26:
                            intended_answer = chr(ord("A") + i - 1)
                        else:
                            intended_answer = str(i)
                    except (TypeError, ValueError):
                        pass
        else:
            if isinstance(problem_block, str) and problem_block.strip():
                question = problem_block
            else:
                question = ""
            question = (
                question
                or data.get("question")
                or data.get("stem")
                or data.get("problem")
                or data.get("prompt")
                or ""
            )
            raw_options = (
                data.get("options")
                or data.get("choices")
                or data.get("select_options")
                or data.get("answer_choices")
                or []
            )
            intended_answer = (
                data.get("intended_answer")
                or data.get("answer")
                or data.get("correct_answer")
                or data.get("correct_choice")
                or data.get("correct_option")
                or data.get("correct")
                or ""
            )
            if not intended_answer:
                idx = data.get("correct_choice_index")
                if idx is not None:
                    try:
                        i = int(idx)
                        if 1 <= i <= 26:
                            intended_answer = chr(ord("A") + i - 1)
                        else:
                            intended_answer = str(i)
                    except (TypeError, ValueError):
                        pass

        if isinstance(intended_answer, int):
            if 1 <= intended_answer <= 5:
                intended_answer = str(intended_answer)
            elif 0 <= intended_answer <= 4:
                intended_answer = str(intended_answer + 1)
            else:
                intended_answer = str(intended_answer)

        if isinstance(raw_options, list) and raw_options and isinstance(raw_options[0], dict):
            raw_options = [
                str(opt.get("text") or opt.get("label") or opt.get("value") or opt.get("id") or "")
                for opt in raw_options
            ]

        intended_solution_path = (
            solution_block.get("outline")
            if isinstance(solution_block, dict)
            else None
        ) or (
            data.get("intended_solution_path")
            or data.get("solution_path")
            or data.get("explanation_steps")
            or data.get("solution")
            or []
        )

        if isinstance(solution_block, dict) and solution_block.get("answer_value") and not intended_answer:
            intended_answer = solution_block.get("answer_value")

        target_concepts = (
            diagnostic_block.get("skills")
            if isinstance(diagnostic_block, dict)
            else None
        ) or (
            data.get("target_concepts")
            or data.get("skills_assessed")
            or data.get("skills")
            or data.get("concepts")
            or data.get("concept_ontology")
            or []
        )

        prerequisites = (
            data.get("prerequisites")
            or data.get("prerequisite_concepts")
            or []
        )

        difficulty_rationale = (
            data.get("difficulty_rationale")
            or data.get("difficulty_reason")
            or ""
        )

        uniqueness_assumption = (
            data.get("uniqueness_assumption")
            or data.get("uniqueness")
            or data.get("unique_solution")
            or ""
        )

        metadata = data.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        metadata = {
            **metadata,
            "grade": metadata.get("grade", data.get("grade", "")),
            "semester": metadata.get("semester", data.get("semester", "")),
            "course": metadata.get("course", data.get("course", "")),
            "unit": metadata.get("unit", data.get("unit", "")),
            "topic": metadata.get("topic", data.get("topic", "")),
            "difficulty": metadata.get(
                "difficulty",
                data.get("difficulty_target", data.get("difficulty", "")),
            ),
            "item_type": metadata.get("item_type", data.get("item_type", "")),
            "purpose": metadata.get("purpose", data.get("purpose", "")),
            "language": metadata.get("language", data.get("language", "")),
        }

        return {
            "message_type": "problem_draft",
            "request_id": data.get("request_id", ""),
            "draft_version": int(
                data.get(
                    "draft_version",
                    data.get("version", metadata.get("draft_version", 1)),
                )
            ),
            "metadata": _normalize_metadata(metadata),
            "question": str(question),
            "options": _to_str_list(raw_options),
            "intended_answer": str(intended_answer),
            "intended_solution_path": _to_str_list(intended_solution_path),
            "target_concepts": _to_str_list(target_concepts),
            "prerequisites": _to_str_list(prerequisites),
            "difficulty_rationale": str(difficulty_rationale),
            "uniqueness_assumption": str(uniqueness_assumption),
        }

    return data


class LLMClient:
    def __init__(self, model_name: str | None = None) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-5")
        self.client = OpenAI(api_key=api_key)

    def structured_generate(
        self,
        *,
        system_prompt: str,
        user_payload: Dict[str, Any],
        response_model: Type[T],
    ) -> T:
        response = self.client.responses.create(
            model=self.model_name,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        )

        content = response.output_text
        print("=== RAW LLM OUTPUT ===")
        print(content)

        data = json.loads(content)
        normalized = _normalize_for_model(data, response_model.__name__)

        print("=== NORMALIZED ===")
        print(normalized)

        return response_model.model_validate(normalized)