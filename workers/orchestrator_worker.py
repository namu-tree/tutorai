from __future__ import annotations

import pathlib
import sys

PROJECT_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import asyncio
import json
import os
import uuid
from typing import Any, Dict, Optional

from core.models import (
    AgentCommand,
    ConceptLight,
    ConceptStatusUpdate,
    FinalProblemPackage,
    SessionState,
    SessionUpdate,
    SessionUpdateType,
    StudentEvent,
    StudentEventType,
    TaskSpec,
)
from core.rules import DecisionRules
from services.bus import BusConfig, RedisBus
from services.event_store import SQLiteEventStore


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _concept_names_from_problem(pkg: FinalProblemPackage) -> list[str]:
    names: list[str] = []
    if isinstance(pkg.concept_ontology, list):
        for item in pkg.concept_ontology:
            if isinstance(item, dict) and "name" in item:
                names.append(str(item["name"]))
            elif isinstance(item, str):
                names.append(item)
    return names if names else ["미분류"]


class OrchestratorWorker:
    def __init__(self) -> None:
        self.bus = RedisBus(BusConfig.from_env())
        self.store = SQLiteEventStore()

    async def _publish(self, update: SessionUpdate) -> None:
        self.store.append_session_update(update)
        await self.bus.publish_session_update(update)

    async def _agent_call(
        self, *, session_id: str, agent_name: str, payload: Dict[str, Any], timeout_s: int = 120
    ) -> Dict[str, Any]:
        cmd = AgentCommand(
            command_id=_new_id("cmd"),
            session_id=session_id,
            agent_name=agent_name,
            payload=payload,
        )
        await self.bus.enqueue_agent_command(cmd)
        result = await self.bus.wait_agent_result(
            command_id=cmd.command_id,
            session_id=session_id,
            block_ms=2000,
            max_wait_s=timeout_s,
        )
        if not result.ok:
            raise RuntimeError(f"{agent_name} 실패: {result.error}")
        return result.result

    async def _run_generation_pipeline(self, session_id: str, task_spec: TaskSpec) -> None:
        # 1) Curriculum
        await self._publish(
            SessionUpdate(
                update_id=_new_id("upd"),
                session_id=session_id,
                update_type=SessionUpdateType.STATUS,
                data={"stage": "curriculum", "message": "교육과정 검토 중"},
            )
        )
        curriculum = await self._agent_call(
            session_id=session_id, agent_name="CurriculumAgent", payload=task_spec.model_dump()
        )
        if curriculum.get("curriculum_fit") != "pass":
            await self._publish(
                SessionUpdate(
                    update_id=_new_id("upd"),
                    session_id=session_id,
                    update_type=SessionUpdateType.ERROR,
                    data={"message": "교육과정 적합성 검토 실패", "curriculum": curriculum},
                )
            )
            return

        # 2) Revision loop
        revision_history: list[dict[str, str]] = []
        last_solver = None
        last_critic = None
        last_student = None
        draft = None

        for round_idx in range(1, task_spec.constraints.max_revision_rounds + 1):
            await self._publish(
                SessionUpdate(
                    update_id=_new_id("upd"),
                    session_id=session_id,
                    update_type=SessionUpdateType.STATUS,
                    data={"stage": "design", "round": round_idx, "message": "문항 초안 생성 중"},
                )
            )
            draft = await self._agent_call(
                session_id=session_id,
                agent_name="ProblemDesignerAgent",
                payload={
                    "task_spec": task_spec.model_dump(),
                    "curriculum": curriculum,
                    "draft_version": round_idx,
                },
            )

            await self._publish(
                SessionUpdate(
                    update_id=_new_id("upd"),
                    session_id=session_id,
                    update_type=SessionUpdateType.STATUS,
                    data={"stage": "solve", "round": round_idx, "message": "풀이/유일성 점검 중"},
                )
            )
            last_solver = await self._agent_call(
                session_id=session_id, agent_name="SolverAgent", payload=draft
            )

            await self._publish(
                SessionUpdate(
                    update_id=_new_id("upd"),
                    session_id=session_id,
                    update_type=SessionUpdateType.STATUS,
                    data={"stage": "critic", "round": round_idx, "message": "품질 검토 중"},
                )
            )
            last_critic = await self._agent_call(
                session_id=session_id,
                agent_name="CriticAgent",
                payload={"draft": draft, "solver": last_solver, "curriculum": curriculum},
            )

            last_student = None
            if task_spec.student_profile is not None:
                await self._publish(
                    SessionUpdate(
                        update_id=_new_id("upd"),
                        session_id=session_id,
                        update_type=SessionUpdateType.STATUS,
                        data={"stage": "student", "round": round_idx, "message": "학생 정렬도 점검 중"},
                    )
                )
                last_student = await self._agent_call(
                    session_id=session_id,
                    agent_name="StudentModelAgent",
                    payload={
                        "draft": draft,
                        "solver": last_solver,
                        "student_profile": task_spec.student_profile.model_dump(),
                    },
                )

            # Decision
            from core.models import CriticReport, SolverReport, StudentAlignmentReport  # local import

            decision = DecisionRules.decide(
                task_spec=task_spec,
                solver=SolverReport.model_validate(last_solver),
                critic=CriticReport.model_validate(last_critic),
                student=StudentAlignmentReport.model_validate(last_student) if last_student else None,
                round_idx=round_idx,
            )

            if decision.status.value == "approved":
                revision_history.append({"version": str(round_idx), "status": "approved"})
                final_problem = await self._agent_call(
                    session_id=session_id,
                    agent_name="FinalEditorAgent",
                    payload={
                        "draft": draft,
                        "revision_history": revision_history,
                        "student_check": "pass" if last_student else "not_run",
                    },
                )
                pkg = FinalProblemPackage.model_validate(final_problem)
                await self._publish(
                    SessionUpdate(
                        update_id=_new_id("upd"),
                        session_id=session_id,
                        update_type=SessionUpdateType.PROBLEM_PUBLISHED,
                        data={
                            "final_problem": final_problem,
                            "curriculum": curriculum,
                            "solver": last_solver,
                            "critic": last_critic,
                            "student": last_student,
                        },
                    )
                )
                # 세션에 현재 문항 저장 + 해당 문항 개념들 초록불로 초기화
                state = self.store.get_session(session_id) or SessionState(session_id=session_id)
                state.last_problem = pkg
                names = _concept_names_from_problem(pkg)
                state.concept_status = {n: ConceptLight.GREEN.value for n in names}
                state.last_message = "문항 생성 완료"
                self.store.upsert_session(state)
                return

            if decision.status.value == "rejected":
                revision_history.append(
                    {"version": str(round_idx), "status": "rejected", "reason": decision.reason}
                )
                await self._publish(
                    SessionUpdate(
                        update_id=_new_id("upd"),
                        session_id=session_id,
                        update_type=SessionUpdateType.ERROR,
                        data={
                            "message": decision.reason,
                            "curriculum": curriculum,
                            "solver": last_solver,
                            "critic": last_critic,
                            "student": last_student,
                        },
                    )
                )
                return

            revision_history.append(
                {"version": str(round_idx), "status": "revised", "reason": decision.reason}
            )
            if decision.revision_request:
                task_spec.revision_feedback.extend(decision.revision_request.must_fix)
                task_spec.revision_feedback.extend(decision.revision_request.should_fix)

        await self._publish(
            SessionUpdate(
                update_id=_new_id("upd"),
                session_id=session_id,
                update_type=SessionUpdateType.ERROR,
                data={"message": "최대 수정 횟수를 초과하여 반려됨"},
            )
        )

    async def handle_event(self, event: StudentEvent) -> None:
        self.store.append_student_event(event)

        # Ensure session exists
        state = self.store.get_session(event.session_id) or SessionState(session_id=event.session_id)
        state.updated_at = event.created_at

        if event.event_type == StudentEventType.SESSION_STARTED:
            task_spec = TaskSpec.model_validate(event.payload["task_spec"])
            state.task_spec = task_spec
            state.last_message = "세션 시작"
            self.store.upsert_session(state)

            await self._publish(
                SessionUpdate(
                    update_id=_new_id("upd"),
                    session_id=event.session_id,
                    update_type=SessionUpdateType.STATUS,
                    data={"message": "세션이 생성되었습니다.", "session_id": event.session_id},
                )
            )
            await self._run_generation_pipeline(event.session_id, task_spec)
            return

        # Other events: ACK + (선택)추가 처리
        self.store.upsert_session(state)
        await self._publish(
            SessionUpdate(
                update_id=_new_id("upd"),
                session_id=event.session_id,
                update_type=SessionUpdateType.STATUS,
                data={"message": "이벤트 수신", "event_type": event.event_type.value},
            )
        )

        # 힌트 요청 → 해당 문항의 개념을 노란불로 바꾸고 힌트 내용 반환
        if event.event_type == StudentEventType.HINT_REQUESTED:
            state = self.store.get_session(event.session_id) or SessionState(session_id=event.session_id)
            hint_text = "풀이 방향을 생각해 보세요."
            concept_status_updates: list[dict] = []
            if state.last_problem:
                names = _concept_names_from_problem(state.last_problem)
                for n in names:
                    state.concept_status[n] = ConceptLight.YELLOW.value
                    concept_status_updates.append(ConceptStatusUpdate(concept=n, status=ConceptLight.YELLOW).model_dump())
                if state.last_problem.explanation:
                    hint_text = state.last_problem.explanation.strip().split("\n")[0] or hint_text
                elif getattr(state.last_problem, "question", None):
                    hint_text = "지문에서 요구하는 것을 먼저 식으로 나타내 보세요."
            self.store.upsert_session(state)
            await self._publish(
                SessionUpdate(
                    update_id=_new_id("upd"),
                    session_id=event.session_id,
                    update_type=SessionUpdateType.HINT,
                    data={
                        "hint": hint_text,
                        "concept_status_updates": concept_status_updates,
                    },
                )
            )
            await self._publish(
                SessionUpdate(
                    update_id=_new_id("upd"),
                    session_id=event.session_id,
                    update_type=SessionUpdateType.CONCEPT_STATUS,
                    data={"concept_status": state.concept_status},
                )
            )

        # 제출(오답) → 오답 분석 + 해당 개념 빨간불/노란불 + 다음 문항 난이도 제안
        if event.event_type == StudentEventType.SUBMITTED:
            state = self.store.get_session(event.session_id) or SessionState(session_id=event.session_id)
            selected = event.payload.get("selected_answer") or event.payload.get("answer_index")
            correct = None
            if state.last_problem:
                correct = state.last_problem.answer
            if correct is not None and selected is not None and str(selected).strip() != str(correct).strip():
                names = _concept_names_from_problem(state.last_problem) if state.last_problem else []
                for n in names:
                    state.concept_status[n] = ConceptLight.RED.value
                state.suggested_difficulty = "Level 1"
                self.store.upsert_session(state)
                concept_status_updates = [
                    ConceptStatusUpdate(concept=n, status=ConceptLight.RED).model_dump() for n in names
                ]
                analysis = f"선택한 답은 {selected}번입니다. 정답은 {correct}번입니다. 이 문항의 핵심 개념을 다시 확인해 보세요."
                if names:
                    analysis += f" (관련 개념: {', '.join(names)})"
                await self._publish(
                    SessionUpdate(
                        update_id=_new_id("upd"),
                        session_id=event.session_id,
                        update_type=SessionUpdateType.FEEDBACK,
                        data={
                            "wrong_answer_analysis": analysis,
                            "correct_answer": correct,
                            "selected_answer": selected,
                            "concept_status_updates": concept_status_updates,
                            "suggested_difficulty": state.suggested_difficulty,
                        },
                    )
                )
                await self._publish(
                    SessionUpdate(
                        update_id=_new_id("upd"),
                        session_id=event.session_id,
                        update_type=SessionUpdateType.CONCEPT_STATUS,
                        data={"concept_status": state.concept_status},
                    )
                )
            elif correct is not None and selected is not None and str(selected).strip() == str(correct).strip():
                state.suggested_difficulty = "Level 2"
                self.store.upsert_session(state)
                await self._publish(
                    SessionUpdate(
                        update_id=_new_id("upd"),
                        session_id=event.session_id,
                        update_type=SessionUpdateType.FEEDBACK,
                        data={
                            "correct": True,
                            "message": "정답입니다.",
                            "suggested_difficulty": state.suggested_difficulty,
                        },
                    )
                )

    async def run(self) -> None:
        cfg = self.bus.config
        stream_key = cfg.stream_student_events()
        group = os.getenv("STUDENT_EVENTS_GROUP", "orchestrators")
        consumer = os.getenv("STUDENT_EVENTS_CONSUMER", "orchestrator_1")

        r = self.bus._redis
        try:
            await r.xgroup_create(stream_key, group, id="0-0", mkstream=True)
        except Exception:
            pass

        last_id = ">"
        while True:
            resp = await r.xreadgroup(group, consumer, {stream_key: last_id}, count=10, block=5000)
            if not resp:
                continue
            _, entries = resp[0]
            for entry_id, fields in entries:
                raw = fields.get("event")
                if not raw:
                    await r.xack(stream_key, group, entry_id)
                    continue
                try:
                    event = StudentEvent.model_validate_json(raw)
                except Exception:
                    event = StudentEvent.model_validate(json.loads(raw))

                try:
                    await self.handle_event(event)
                except Exception as e:
                    await self._publish(
                        SessionUpdate(
                            update_id=_new_id("upd"),
                            session_id=event.session_id,
                            update_type=SessionUpdateType.ERROR,
                            data={"message": f"워크플로우 처리 실패: {e}"},
                        )
                    )
                finally:
                    await r.xack(stream_key, group, entry_id)


async def main() -> None:
    worker = OrchestratorWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

