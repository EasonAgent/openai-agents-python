""" 
- [x] function_tool
- [x] HostedMCPTool -- openai Responses API!
- [ ] CodeInterpreterTool
- [ ] LocalShellTool
- [ ] ImageGenerationTool
"""

import abc
import inspect
from typing import Any, Awaitable, Callable, Union, Literal, Generic
from typing_extensions import TypeVar, TypeAlias, Concatenate, ParamSpec, NotRequired
from dataclasses import dataclass, field

from pydantic import BaseModel

from .run import RunContextWrapper, TContext, MaybeAwaitable
from .item import RunItem, TResponseInputItem
from .agent import Agent

""" --------------------------------------------------------------------------------------------------------------------
ToolContext: 工具上下文
-------------------------------------------------------------------------------------------------------------------- """
# agent/tool_context.py
@dataclass
class ToolContext(RunContextWrapper[TContext]):
    """The context of a tool call."""
    tool_call_id: str = field(default_factory=_assert_must_pass_tool_call_id)
    @classmethod
    def from_agent_context(cls, context: RunContextWrapper[TContext], tool_call_id: str) -> "ToolContext":
        """ Create a ToolContext from a RunContextWrapper. """

def _assert_must_pass_tool_call_id() -> str:
    raise ValueError("tool_call_id must be passed to ToolContext")


""" --------------------------------------------------------------------------------------------------------------------
Tool: 工具定义
    工具定义: name, description, params_json_schema
    工具调用: on_invoke_tool
    输入输出: 均为 str
-------------------------------------------------------------------------------------------------------------------- """
Tool = Union[FunctionTool, FileSearchTool, WebSearchTool, ComputerTool]

# --------------------------------------------------------------------------------
# FunctionTool: 函数工具
# --------------------------------------------------------------------------------
@dataclass
class FunctionTool:
    name: str
    description: str
    params_json_schema: dict[str, Any]
    on_invoke_tool: Callable[[RunContextWrapper[Any], str], Awaitable[Any]]
    strict_json_schema: bool = True


# --------------------------------------------------------------------------------
# 接入openai包支持的工具
# --------------------------------------------------------------------------------
from openai.types.responses.file_search_tool_param import Filters, RankingOptions
from openai.types.responses.web_search_tool_param import UserLocation
@dataclass
class ComputerTool:
    computer: Computer | AsyncComputer
    def name(self): ...
@dataclass
class FileSearchTool:
    vector_store_ids: list[str]
    max_num_results: int | None = None
    include_search_results: bool = False
    ranking_options: RankingOptions | None = None
    filters: Filters | None = None
    def name(self): ...
@dataclass
class WebSearchTool:
    user_location: UserLocation | None = None
    search_context_size: Literal["low", "medium", "high"] = "medium"
    def name(self): ...
# 辅助: 对于computer的抽象
Environment = Literal["mac", "windows", "ubuntu", "browser"]
Button = Literal["left", "right", "wheel", "back", "forward"]
class Computer(abc.ABC): ...
class AsyncComputer(abc.ABC): ...

from openai.types.responses.tool_param import Mcp
from openai.types.responses.response_output_item import LocalShellCall, McpApprovalRequest
@dataclass
class HostedMCPTool:
    """A tool that allows the LLM to use a remote MCP server. The LLM will automatically list and
    call tools, without requiring a a round trip back to your code.
    If you want to run MCP servers locally via stdio, in a VPC or other non-publicly-accessible
    environment, or you just prefer to run tool calls locally, then you can instead use the servers
    in `agents.mcp` and pass `Agent(mcp_servers=[...])` to the agent."""
    tool_config: Mcp
    on_approval_request: MCPToolApprovalFunction | None = None
    @property
    def name(self):
        return "hosted_mcp"

MCPToolApprovalFunction = Callable[[MCPToolApprovalRequest], MaybeAwaitable[MCPToolApprovalFunctionResult]]
@dataclass
class MCPToolApprovalRequest:
    """A request to approve a tool call."""
    ctx_wrapper: RunContextWrapper[Any]
    data: McpApprovalRequest
class MCPToolApprovalFunctionResult(TypedDict):
    """The result of an MCP tool approval function."""
    approve: bool
    reason: NotRequired[str]


# --------------------------------------------------------------------------------
# function_tool
# 1. 支持异步/同步; 2) 错误处理
# --------------------------------------------------------------------------------
def function_tool(
    func: ToolFunction[...] | None = None,
    *,
    name_override: str | None = None,
    description_override: str | None = None,
    docstring_style: DocstringStyle | None = None,
    use_docstring_info: bool = True,
    failure_error_function: ToolErrorFunction | None = default_tool_error_function,
    strict_mode: bool = True,
    is_enabled: bool | Callable[[RunContextWrapper[Any], Agent[Any]], MaybeAwaitable[bool]] = True,
) -> FunctionTool | Callable[[ToolFunction[...]], FunctionTool]:
    """
    Decorator to create a FunctionTool from a function. By default, we will:
    1. Parse the function signature to create a JSON schema for the tool's parameters.
    2. Use the function's docstring to populate the tool's description.
    3. Use the function's docstring to populate argument descriptions.
    The docstring style is detected automatically, but you can override it.

    If the function takes a `RunContextWrapper` as the first argument, it *must* match the context type of the agent that uses the tool.
    """
    # 内容调用 `function_schema` 工具

ToolParams = ParamSpec("ToolParams")

ToolFunctionWithoutContext = Callable[ToolParams, Any]
ToolFunctionWithContext = Callable[Concatenate[RunContextWrapper[Any], ToolParams], Any]
ToolFunctionWithToolContext = Callable[Concatenate[ToolContext, ToolParams], Any]
ToolFunction = Union[ToolFunctionWithoutContext[ToolParams], ToolFunctionWithContext[ToolParams], ToolFunctionWithToolContext[ToolParams]]

DocstringStyle = Literal["google", "numpy", "sphinx"]

ToolErrorFunction = Callable[[RunContextWrapper[Any], Exception], MaybeAwaitable[str]]

def default_tool_error_function(ctx: RunContextWrapper[Any], error: Exception) -> str:
    """The default tool error function, which just returns a generic error message."""
    return f"An error occurred while running the tool. Please try again. Error: {str(error)}"


# agents/function_schema.py
def function_schema(
    func: Callable[..., Any],
    docstring_style: DocstringStyle | None = None,
    name_override: str | None = None,
    description_override: str | None = None,
    use_docstring_info: bool = True,
    strict_json_schema: bool = True,
) -> FuncSchema:
    """Given a python function, extracts a `FuncSchema` from it, capturing the name, description,
    parameter descriptions, and other metadata."""

@dataclass
class FuncSchema:
    """ Captures the schema for a python function, in preparation for sending it to an LLM as a tool. """
    name: str
    description: str | None
    params_pydantic_model: type[BaseModel]
    params_json_schema: dict[str, Any]
    signature: inspect.Signature
    takes_context: bool = False  # Whether the function takes a RunContextWrapper argument (must be the first argument).
    strict_json_schema: bool = True

    def to_call_args(self, data: BaseModel) -> tuple[list[Any], dict[str, Any]]:
        """ Converts validated data from the Pydantic model into (args, kwargs), suitable for calling the original function. """
        # return positional_args, keyword_args


""" --------------------------------------------------------------------------------------------------------------------
Handoff: 
    对于模型而言, 可以看作一个特殊的工具.
    提供一个 handoff 方法将agent转换 Handoff
-------------------------------------------------------------------------------------------------------------------- """
THandoffInput = TypeVar("THandoffInput", default=Any)

class Handoff(Generic[TContext]):
    tool_name: str
    tool_description: str
    input_json_schema: dict[str, Any]
    on_invoke_handoff: Callable[[RunContextWrapper[Any], str], Awaitable[Agent[TContext]]]
    agent_name: str
    input_filter: HandoffInputFilter | None = None
    strict_json_schema: bool = True
    def get_transfer_message(self, agent: Agent[Any]) -> str: ...
    @classmethod
    def default_tool_name(cls, agent: Agent[Any]) -> str: ...
    @classmethod
    def default_tool_description(cls, agent: Agent[Any]) -> str: ...

@dataclass(frozen=True)
class HandoffInputData:
    input_history: str | tuple[TResponseInputItem, ...]
    pre_handoff_items: tuple[RunItem, ...]
    new_items: tuple[RunItem, ...]

HandoffInputFilter: TypeAlias = Callable[[HandoffInputData], HandoffInputData]

OnHandoffWithInput = Callable[[RunContextWrapper[Any], THandoffInput], Any]
OnHandoffWithoutInput = Callable[[RunContextWrapper[Any]], Any]
def handoff(agent: Agent[TContext], tool_name_override: str | None = None, tool_description_override: str | None = None, on_handoff: OnHandoffWithInput[THandoffInput] | OnHandoffWithoutInput | None = None, input_type: type[THandoffInput] | None = None, input_filter: Callable[[HandoffInputData], HandoffInputData] | None = None) -> Handoff[TContext]: ...



# RunImpl.execute_function_tool_calls(...) -> FunctionToolResult
@dataclass
class FunctionToolResult:
    tool: FunctionTool
    output: Any
    run_item: RunItem
