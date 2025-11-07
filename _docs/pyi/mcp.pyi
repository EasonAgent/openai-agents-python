import abc
from typing import Any
import asyncio
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from mcp import ClientSession, StdioServerParameters, Tool as MCPTool, stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import GetSessionIdCallback, streamablehttp_client
from mcp.shared.message import SessionMessage
from mcp.types import CallToolResult

from .run import RunContextWrapper
from .tool import Tool, FunctionTool


""" --------------------------------------------------------------------------------------------------------------------
MCPUtil
-------------------------------------------------------------------------------------------------------------------- """
# src/agents/mcp/util.py
class MCPUtil:
    """Set of utilities for interop between MCP and Agents SDK tools."""
    @classmethod
    async def get_all_function_tools(cls, servers: list["MCPServer"], convert_schemas_to_strict: bool) -> list[Tool]:
        """Get all function tools from a list of MCP servers."""
    @classmethod
    async def get_function_tools(cls, server: "MCPServer", convert_schemas_to_strict: bool) -> list[Tool]:
        """Get all function tools from a single MCP server."""
    @classmethod
    def to_function_tool(cls, tool: "MCPTool", server: "MCPServer", convert_schemas_to_strict: bool) -> FunctionTool:
        """Convert an MCP tool to an Agents SDK function tool."""
    @classmethod
    async def invoke_mcp_tool(cls, server: "MCPServer", tool: "MCPTool", context: RunContextWrapper[Any], input_json: str) -> str:
        """Invoke an MCP tool and return the result as a string."""


""" --------------------------------------------------------------------------------------------------------------------
MCPServer(abc.ABC)
    抽象基类, 仅仅暴露 connect, cleanup, list_tools, call_tool 接口
_MCPServerWithClientSession(MCPServer, abc.ABC)
    统一用 ClientSession 来管理连接, 实现了上面的四个接口
    暴露一个接口来处理连接: create_streams() -> AbstractAsyncContextManager[tuple[MemoryObjectReceiveStream[SessionMessage | Exception], MemoryObjectSendStream[SessionMessage], GetSessionIdCallback | None]]
-------------------------------------------------------------------------------------------------------------------- """
# src/agents/mcp/server.py
class MCPServer(abc.ABC):
    """Base class for Model Context Protocol servers."""
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """A readable name for the server."""

    @abc.abstractmethod
    async def connect(self):
        """Connect to the server. For example, this might mean spawning a subprocess or
        opening a network connection. The server is expected to remain connected until
        `cleanup()` is called.
        """
    @abc.abstractmethod
    async def cleanup(self):
        """Cleanup the server. For example, this might mean closing a subprocess or
        closing a network connection.
        """
    @abc.abstractmethod
    async def list_tools(self) -> list[MCPTool]:
        """List the tools available on the server."""

    @abc.abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None) -> CallToolResult:
        """Invoke a tool on the server."""


class _MCPServerWithClientSession(MCPServer, abc.ABC):
    """Base class for MCP servers that use a `ClientSession` to communicate with the server."""
    def __init__(self, cache_tools_list: bool, client_session_timeout_seconds: float | None):
        self.session: ClientSession | None = None
        self.exit_stack: AsyncExitStack = AsyncExitStack()
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.cache_tools_list = cache_tools_list
        self.server_initialize_result: InitializeResult | None = None
        self.client_session_timeout_seconds = client_session_timeout_seconds

    async def __aenter__(self):
        await self.connect()
        return self
    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.cleanup()

    @abc.abstractmethod
    def create_streams(self) -> AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[SessionMessage | Exception],
            MemoryObjectSendStream[SessionMessage],
            GetSessionIdCallback | None,
        ]
    ]:
        """Create the streams for the server."""

    async def connect(self):
        """Connect to the server."""
        try:
            transport = await self.exit_stack.enter_async_context(self.create_streams())
            # streamablehttp_client returns (read, write, get_session_id)
            # sse_client returns (read, write)
            read, write, *_ = transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write, ...)
            )
            server_result = await session.initialize()
            self.server_initialize_result = server_result
            self.session = session
        except Exception as e:
            raise

    async def list_tools(self) -> list[MCPTool]:
        """List the tools available on the server."""
        self._tools_list = (await self.session.list_tools()).tools
        return self._tools_list
    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None) -> CallToolResult:
        """Invoke a tool on the server."""
        return await self.session.call_tool(tool_name, arguments)

    async def cleanup(self):
        """Cleanup the server."""
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
            except Exception as e:
                logger.error(f"Error cleaning up server: {e}")
            finally:
                self.session = None


class MCPServerStdio(_MCPServerWithClientSession):
    """MCP server implementation that uses the stdio transport. See the [spec]
    (https://spec.modelcontextprotocol.io/specification/2024-11-05/basic/transports/#stdio) for
    details.
    """

class MCPServerSse(_MCPServerWithClientSession):
    """MCP server implementation that uses the HTTP with SSE transport. See the [spec]
    (https://spec.modelcontextprotocol.io/specification/2024-11-05/basic/transports/#http-with-sse)
    for details.
    """

class MCPServerStreamableHttp(_MCPServerWithClientSession):
    """MCP server implementation that uses the Streamable HTTP transport. See the [spec]
    (https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http)
    for details.
    """
