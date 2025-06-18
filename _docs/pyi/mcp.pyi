import abc
from typing import Any

from mcp import ClientSession, StdioServerParameters, Tool as MCPTool, stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import GetSessionIdCallback, streamablehttp_client
from mcp.shared.message import SessionMessage
from mcp.types import CallToolResult

from .run import RunContextWrapper
from .tool import Tool, FunctionTool



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


# src/agents/mcp/server.py
class MCPServer(abc.ABC):
    """Base class for Model Context Protocol servers."""
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

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
