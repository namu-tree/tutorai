from __future__ import annotations

from typing import List


def basic_option_check(options: List[str], answer: str) -> list[str]:
    issues: list[str] = []
    if len(options) != 5:
        issues.append("선택지 수가 5개가 아님")
    if answer not in {"1", "2", "3", "4", "5"}:
        issues.append("정답 번호가 1~5 범위를 벗어남")
    return issues