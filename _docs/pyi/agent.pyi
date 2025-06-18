import abc
from typing import Generic, Callable, Awaitable, Any, Literal
from typing_extensions import TypeVar, TypeAlias, NotRequired
from dataclasses import dataclass, field
import dataclasses

from pydantic import TypeAdapter

from .tool import Tool, FunctionToolResult
from .model import Model, ModelSettings
from .run import RunResult, InputGuardrail, OutputGuardrail, TContext, RunContextWrapper, MaybeAwaitable
from .mcp import MCPServer


""" --------------------------------------------------------------------------------------------------------------------
Agent: 对于一个 agent 的封装
    - instructions: SP, 可以是一个函数!
    - handoffs, handoff_description: 定义自身的调用说明和调用关系
    - model, model_settings: 指定模型
    - tools, mcp_servers, mcp_config: 指定工具
    - tool_use_behavior, reset_tool_choice: 指定工具使用行为
    - input_guardrails, output_guardrails: 指定输入输出检查
    - output_type: 指定输出类型
    - hooks: 指定回调 | lifecycle
-------------------------------------------------------------------------------------------------------------------- """
@dataclass
class Agent(Generic[TContext]):
    name: str
    instructions: (str | Callable[[RunContextWrapper[TContext], Agent[TContext]], MaybeAwaitable[str]]) | None = None
    prompt: Prompt | DynamicPromptFunction | None = None  # NOTE: 仅适用于 responses API
    handoff_description: str | None = None
    handoffs: list[Agent[Any] | Handoff[TContext]] = field(default_factory=list)
    model: str | Model | None = None
    model_settings: ModelSettings = field(default_factory=ModelSettings)
    tools: list[Tool] = field(default_factory=list)
    mcp_servers: list[MCPServer] = field(default_factory=list)
    """A list of [Model Context Protocol](https://modelcontextprotocol.io/) servers that
    the agent can use. Every time the agent runs, it will include tools from these servers in the
    list of available tools.
    NOTE: You are expected to manage the lifecycle of these servers. Specifically, you must call
    `server.connect()` before passing it to the agent, and `server.cleanup()` when the server is no
    longer needed.
    """
    mcp_config: MCPConfig = field(default_factory=lambda: MCPConfig())
    input_guardrails: list[InputGuardrail[TContext]] = field(default_factory=list)
    output_guardrails: list[OutputGuardrail[TContext]] = field(default_factory=list)
    output_type: type[Any] | AgentOutputSchemaBase | None = None
    hooks: AgentHooks[TContext] | None = None
    tool_use_behavior: (Literal["run_llm_again", "stop_on_first_tool"] | StopAtTools | ToolsToFinalOutputFunction) = "run_llm_again"
    reset_tool_choice: bool = True

    def clone(self, **kwargs: Any) -> Agent[TContext]:
        return dataclasses.replace(self, **kwargs)
    def as_tool(self, tool_name: str | None, tool_description: str | None, custom_output_extractor: Callable[[RunResult], Awaitable[str]] | None = None) -> Tool:
        """Transform this agent into a tool, callable by other agents.
        This is different from handoffs in two ways:
        1. In handoffs, the new agent receives the conversation history. In this tool, the new agent
           receives generated input.
        2. In handoffs, the new agent takes over the conversation. In this tool, the new agent is
           called as a tool, and the conversation is continued by the original agent.
        """

    async def get_system_prompt(self, run_context: RunContextWrapper[TContext]) -> str | None:
        """Get the system prompt for the agent."""
    async def get_prompt(self, run_context: RunContextWrapper[TContext]) -> ResponsePromptParam | None:
        """Get the prompt for the agent."""
        # NOTE: 仅适用于 responses API
        return await PromptUtil.to_model_input(self.prompt, run_context, self)

    async def get_mcp_tools(self) -> list[Tool]:
        """Fetches the available tools from the MCP servers."""
    async def get_all_tools(self, run_context: RunContextWrapper[Any]) -> list[Tool]:
        """All agent tools, including MCP tools and function tools."""


class StopAtTools(TypedDict):
    stop_at_tool_names: list[str]

@dataclass
class ToolsToFinalOutputResult:
    is_final_output: bool
    final_output: Any | None = None

ToolsToFinalOutputFunction: TypeAlias = Callable[[RunContextWrapper[TContext], list[FunctionToolResult]], MaybeAwaitable[ToolsToFinalOutputResult]]

class MCPConfig(TypedDict):
    """Configuration for MCP servers."""
    convert_schemas_to_strict: NotRequired[bool]
    """If True, we will attempt to convert the MCP schemas to strict-mode schemas. This is a
    best-effort conversion, so some schemas may not be convertible. Defaults to False.
    """

# --------------------------------------------------------------------------------
# src/agents/agent_output.py
# --------------------------------------------------------------------------------
class AgentOutputSchemaBase(abc.ABC):
    """An object that captures the JSON schema of the output, as well as validating/parsing JSON produced by the LLM into the output type."""
    @abc.abstractmethod
    def is_plain_text(self) -> bool:
        """Whether the output type is plain text (versus a JSON object)."""
    @abc.abstractmethod
    def name(self) -> str:
        """The name of the output type."""
    @abc.abstractmethod
    def json_schema(self) -> dict[str, Any]:
        """Returns the JSON schema of the output. Will only be called if the output type is not plain text."""

    @abc.abstractmethod
    def is_strict_json_schema(self) -> bool:
        """Whether the JSON schema is in strict mode. Strict mode constrains the JSON schema
        features, but guarantees valid JSON. See here for details:
        https://platform.openai.com/docs/guides/structured-outputs#supported-schemas
        """
    @abc.abstractmethod
    def validate_json(self, json_str: str) -> Any:
        """Validate a JSON string against the output type. You must return the validated object,
        or raise a `ModelBehaviorError` if the JSON is invalid.
        """

@dataclass(init=False)
class AgentOutputSchema(AgentOutputSchemaBase):
    _type_adapter: TypeAdapter[Any]
    _is_wrapped: bool
    _output_schema: dict[str, Any]
    strict_json_schema: bool
    def __init__(self, output_type: type[Any], strict_json_schema: bool = True): ...
    def is_plain_text(self) -> bool: ...
    def json_schema(self) -> dict[str, Any]: ...
    def validate_json(self, json_str: str, partial: bool = False) -> Any: ...
    def output_type_name(self) -> str: ...

# --------------------------------------------------------------------------------
# AgentHooks: 建模agent的生命周期
# --------------------------------------------------------------------------------
# 提供了 agent/tool 两种粒度的 hook
class AgentHooks(Generic[TContext]):
    async def on_start(self, context: RunContextWrapper[TContext], agent: Agent[TContext]) -> None: ...
    async def on_end(self, context: RunContextWrapper[TContext], agent: Agent[TContext], output: Any) -> None: ...
    async def on_handoff(self, context: RunContextWrapper[TContext], agent: Agent[TContext], source: Agent[TContext]) -> None: ...
    async def on_tool_start(self, context: RunContextWrapper[TContext], agent: Agent[TContext], tool: Tool) -> None: ...
    async def on_tool_end(self, context: RunContextWrapper[TContext], agent: Agent[TContext], tool: Tool, result: str) -> None: ...


