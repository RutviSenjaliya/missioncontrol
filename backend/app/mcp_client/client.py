"""MCP client used by the agent. Talks to the self-hosted MCP server over Streamable HTTP.

The agent never calls application services for tool work directly: every tool action goes
through this client, so what the agent does is exactly what any MCP client could do.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class MCPUnavailable(Exception):
    pass


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any] | None
    error: str | None
    raw_text: str = ""


@dataclass
class MCPConnection:
    session: ClientSession
    protocol_version: str
    server_name: str
    server_version: str
    tools: dict[str, dict[str, Any]] = field(default_factory=dict)
    tool_timeout: float = 20.0

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name not in self.tools:
            return ToolResult(False, None, f"unknown_tool: '{name}' was not advertised by the MCP server")
        try:
            with anyio.fail_after(self.tool_timeout):
                res = await self.session.call_tool(name, arguments, read_timeout_seconds=timedelta(seconds=self.tool_timeout))
        except TimeoutError:
            return ToolResult(False, None, f"timeout: '{name}' exceeded {self.tool_timeout}s")
        text = "\n".join(getattr(c, "text", "") for c in res.content if getattr(c, "type", "") == "text")
        if res.isError:
            return ToolResult(False, None, text or "tool returned an error", text)
        data = res.structuredContent
        if data is None and text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = {"text": text}
        # FastMCP wraps non-object return types in {"result": ...}; our tools return objects.
        return ToolResult(True, data or {}, None, text)


@asynccontextmanager
async def connect(url: str, token: str, tool_timeout: float = 20.0, connect_timeout: float = 10.0) -> AsyncIterator[MCPConnection]:
    """Open a Streamable HTTP MCP session: initialize (capability negotiation) + tools/list.

    Connection/protocol failures become MCPUnavailable. Exceptions raised by the caller's
    own code inside the `async with` block are re-raised unchanged.
    """
    headers = {"Authorization": f"Bearer {token}"}
    body_error: BaseException | None = None
    try:
        async with streamablehttp_client(url, headers=headers, timeout=connect_timeout) as (read, write, _sid):
            async with ClientSession(read, write) as session:
                with anyio.fail_after(connect_timeout):
                    init = await session.initialize()
                    listed = await session.list_tools()
                conn = MCPConnection(
                    session=session,
                    protocol_version=str(init.protocolVersion),
                    server_name=init.serverInfo.name,
                    server_version=init.serverInfo.version,
                    tools={t.name: {"description": t.description, "input_schema": t.inputSchema} for t in listed.tools},
                    tool_timeout=tool_timeout,
                )
                try:
                    yield conn
                except BaseException as be:
                    body_error = be
                    raise
    except BaseException as e:
        if body_error is not None:
            raise body_error
        if isinstance(e, (KeyboardInterrupt, SystemExit, GeneratorExit, MCPUnavailable)):
            raise
        inner: BaseException = e
        while isinstance(inner, BaseExceptionGroup) and inner.exceptions:
            inner = inner.exceptions[0]
        raise MCPUnavailable(f"MCP server unavailable at {url}: {type(inner).__name__}: {inner}") from e
