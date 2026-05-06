#Node js required for npx
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import uuid4

from acp import (
    Agent,
    InitializeResponse,
    NewSessionResponse,
    PromptResponse,
    run_agent,
    update_agent_message,
    text_block,
)
from acp.interfaces import Client
from acp.schema import ClientCapabilities, Implementation

from common.config import config
from memory.db import DB
from tools.manager import all_tools
from agent.loop import Agent as CustomAgent

cfg = config()
db = DB()
executor = ThreadPoolExecutor(max_workers=4)

# session_id -> CustomAgent; lives for the lifetime of this process
_sessions: dict[str, CustomAgent] = {}


def _get_session(session_id: str) -> CustomAgent:
    if session_id not in _sessions:
        _sessions[session_id] = CustomAgent(cfg, tools=all_tools, db=db, user_id=session_id)
        print(f"[acp_agent] new CustomAgent for session {session_id[:8]}", file=sys.stderr)
    return _sessions[session_id]


class MyAgent(Agent):
    _conn: Client

    def on_connect(self, conn: Client) -> None:
        self._conn = conn

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        return InitializeResponse(protocol_version=protocol_version)

    async def new_session(self, cwd: str, mcp_servers: list, **kwargs: Any) -> NewSessionResponse:
        session_id = uuid4().hex
        _get_session(session_id)
        return NewSessionResponse(session_id=session_id)

    async def prompt(self, prompt: list, session_id: str, **kwargs: Any) -> PromptResponse:
        parts = []
        for block in prompt:
            text = block.text if hasattr(block, "text") else (block.get("text") if isinstance(block, dict) else None)
            if text:
                parts.append(text)
        user_text = " ".join(parts).strip()

        if not user_text:
            return PromptResponse(stop_reason="end_turn")

        agent = _get_session(session_id)

        try:
            loop = asyncio.get_running_loop()
            reply = await loop.run_in_executor(executor, agent.run, user_text)

            if reply:
                await self._conn.session_update(
                    session_id=session_id,
                    update=update_agent_message(text_block(reply)),
                    source="custom-agent",
                )
        except Exception as e:
            print(f"[acp_agent] prompt error: {e}", file=sys.stderr)
            try:
                await self._conn.session_update(
                    session_id=session_id,
                    update=update_agent_message(text_block(f"Error: {e}")),
                    source="custom-agent",
                )
            except Exception:
                pass

        return PromptResponse(stop_reason="end_turn")


async def main() -> None:
    await run_agent(MyAgent())


if __name__ == "__main__":
    asyncio.run(main())
