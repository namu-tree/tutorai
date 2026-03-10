"""
공식 교육과정 범위 데이터 로더.
data/curriculum_scope.json 을 읽어 학년·단원별 허용/금지 개념을 반환한다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SCOPE_PATH = Path(__file__).resolve().parents[1] / "data" / "curriculum_scope.json"
_CACHE: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        with open(_SCOPE_PATH, "r", encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def get_scope(grade: str, unit: str) -> dict[str, Any] | None:
    """
    학년(중1, 중2, 중3, 고1, 고2 등)과 단원명으로
    공식 교육과정 범위를 반환한다.
    반환: { "allowed_concepts": [...], "forbidden_concepts": [...], "notes": str } 또는 None
    """
    data = _load()
    grades = data.get("grades") or {}
    grade_data = grades.get(grade)
    if not grade_data:
        return None
    units = grade_data.get("units") or {}
    scope = units.get(unit)
    if scope:
        return {
            "allowed_concepts": scope.get("allowed_concepts") or [],
            "forbidden_concepts": scope.get("forbidden_concepts") or [],
            "notes": scope.get("notes") or "",
        }
    return None


def get_scope_for_prompt(grade: str, unit: str) -> str:
    """
    Curriculum/Designer 프롬프트에 넣을 문자열을 반환한다.
    해당 학년·단원에 대한 공식 범위가 있으면 그 내용을, 없으면 빈 문자열.
    """
    scope = get_scope(grade, unit)
    if not scope:
        return ""
    lines = [
        "[해당 학년·단원의 공식 교육과정 범위 (반드시 준수)]",
        "허용 개념: " + ", ".join(scope["allowed_concepts"][:15]),
        "금지 개념: " + ", ".join(scope["forbidden_concepts"][:15]),
    ]
    if scope.get("notes"):
        lines.append("참고: " + scope["notes"])
    return "\n".join(lines)
