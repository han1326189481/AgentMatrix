from typing import AsyncGenerator
from fastapi import Depends
from agents.base.agent_registry import AgentRegistry

_agent_registry = None


def get_agent_registry() -> AgentRegistry:
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry


async def get_agent_registry_async() -> AsyncGenerator[AgentRegistry, None]:
    registry = get_agent_registry()
    yield registry