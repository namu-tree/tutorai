from __future__ import annotations

import uuid
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from core.models import (
    GenerationResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionState,
    SessionUpdate,
    SessionUpdateType,
    StudentEvent,
    StudentEventType,
    TaskSpec,
)
from core.orchestrator import Orchestrator
from services.bus import RedisBus
from services.event_store import SQLiteEventStore

router = APIRouter(prefix="/api")
orchestrator = Orchestrator()
bus = RedisBus()
store = SQLiteEventStore()


@router.post("/generate-problem", response_model=GenerationResponse)
def generate_problem(task_spec: TaskSpec) -> GenerationResponse:
    return orchestrator.generate(task_spec)


class StudentEventIn(BaseModel):
    event_type: StudentEventType
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(req: SessionCreateRequest) -> SessionCreateResponse:
    session_id = f"sess_{uuid.uuid4().hex}"
    # Persist session state
    store.upsert_session(SessionState(session_id=session_id, task_spec=req.task_spec, last_message="created"))

    # Enqueue session_started event for orchestrator worker
    ev = StudentEvent(
        event_id=f"evt_{uuid.uuid4().hex}",
        session_id=session_id,
        event_type=StudentEventType.SESSION_STARTED,
        payload={"task_spec": req.task_spec.model_dump()},
    )
    store.append_student_event(ev)
    await bus.enqueue_student_event(ev)
    return SessionCreateResponse(session_id=session_id)


@router.get("/sessions/{session_id}", response_model=SessionState)
async def get_session(session_id: str) -> SessionState:
    state = store.get_session(session_id)
    if state is None:
        # Keep it simple for MVP: create empty view
        return SessionState(session_id=session_id, last_message="not_found")
    return state


@router.post("/sessions/{session_id}/events")
async def post_event(session_id: str, ev_in: StudentEventIn) -> dict:
    ev = StudentEvent(
        event_id=f"evt_{uuid.uuid4().hex}",
        session_id=session_id,
        event_type=ev_in.event_type,
        payload=ev_in.payload,
    )
    store.append_student_event(ev)
    await bus.enqueue_student_event(ev)
    return {"ok": True, "event_id": ev.event_id}


@router.get("/sessions/{session_id}/stream")
async def stream_session(session_id: str) -> StreamingResponse:
    async def gen():
        # Initial hello
        yield (
            "event: status\n"
            f"data: {SessionUpdate(update_id='init', session_id=session_id, update_type=SessionUpdateType.STATUS, data={'message':'connected'}).model_dump_json()}\n\n"
        )
        async for update in bus.subscribe_session_updates(session_id):
            yield f"event: {update.update_type.value}\n"
            yield f"data: {update.model_dump_json()}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")