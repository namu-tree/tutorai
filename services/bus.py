from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, Optional

import redis.asyncio as redis

from core.models import AgentCommand, AgentResult, SessionUpdate, StudentEvent


@dataclass(frozen=True)
class BusConfig:
    redis_url: str
    namespace: str = "tutorai"

    @staticmethod
    def from_env() -> "BusConfig":
        return BusConfig(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            namespace=os.getenv("BUS_NAMESPACE", "tutorai"),
        )

    def key(self, suffix: str) -> str:
        return f"{self.namespace}:{suffix}"

    def stream_student_events(self) -> str:
        return self.key("student_events")

    def stream_agent_commands(self) -> str:
        return self.key("agent_commands")

    def stream_agent_results(self) -> str:
        return self.key("agent_results")

    def channel_session_updates(self, session_id: str) -> str:
        return self.key(f"sessions:{session_id}:updates")


class RedisBus:
    def __init__(self, config: Optional[BusConfig] = None) -> None:
        self.config = config or BusConfig.from_env()
        self._redis = redis.from_url(self.config.redis_url, decode_responses=True)

    async def ping(self) -> bool:
        return bool(await self._redis.ping())

    async def close(self) -> None:
        await self._redis.aclose()

    async def enqueue_student_event(self, event: StudentEvent) -> str:
        key = self.config.stream_student_events()
        return await self._redis.xadd(key, {"event": event.model_dump_json()})

    async def publish_session_update(self, update: SessionUpdate) -> int:
        ch = self.config.channel_session_updates(update.session_id)
        payload = update.model_dump_json()
        # pubsub fan-out for SSE connections
        return await self._redis.publish(ch, payload)

    async def subscribe_session_updates(
        self, session_id: str
    ) -> AsyncGenerator[SessionUpdate, None]:
        ch = self.config.channel_session_updates(session_id)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(ch)
        try:
            async for message in pubsub.listen():
                if message is None or message.get("type") != "message":
                    continue
                data = message.get("data")
                if not data:
                    continue
                try:
                    yield SessionUpdate.model_validate_json(data)
                except Exception:
                    # As a fallback, try JSON parse then validate
                    yield SessionUpdate.model_validate(json.loads(data))
        finally:
            try:
                await pubsub.unsubscribe(ch)
            finally:
                await pubsub.aclose()

    async def enqueue_agent_command(self, cmd: AgentCommand) -> str:
        key = self.config.stream_agent_commands()
        return await self._redis.xadd(key, {"command": cmd.model_dump_json()})

    async def enqueue_agent_result(self, result: AgentResult) -> str:
        key = self.config.stream_agent_results()
        return await self._redis.xadd(key, {"result": result.model_dump_json()})

    async def wait_agent_result(
        self,
        *,
        command_id: str,
        session_id: str,
        block_ms: int = 10_000,
        max_wait_s: int = 60,
    ) -> AgentResult:
        """
        Poll agent_results stream until matching command_id arrives.
        Simple MVP approach: scan forward by XREAD from last_id.
        """
        key = self.config.stream_agent_results()
        last_id = "0-0"
        waited = 0
        while waited < max_wait_s * 1000:
            resp = await self._redis.xread({key: last_id}, block=block_ms, count=50)
            waited += block_ms
            if not resp:
                continue
            _, entries = resp[0]
            for entry_id, fields in entries:
                last_id = entry_id
                raw = fields.get("result")
                if not raw:
                    continue
                try:
                    result = AgentResult.model_validate_json(raw)
                except Exception:
                    result = AgentResult.model_validate(json.loads(raw))
                if result.command_id == command_id and result.session_id == session_id:
                    return result
        raise TimeoutError(f"AgentResult timeout: command_id={command_id}")

