import dataclasses
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Literal, TypeAlias, TypedDict, Union

from .run import TContext, RunContextWrapper
from .tool import Tool, Handoff, FunctionToolResult
from .models import ModelSettings, Model
from .lifecycle import AgentHooks
from .utils import MaybeAwaitable
from .guardrail import InputGuardrail, OutputGuardrail

""" --------------------------------------------------------------------------------------------------------------------
Agent: 对于一个 agent 的封装
-------------------------------------------------------------------------------------------------------------------- """

@dataclass
class Agent(Generic[TContext]):
    name: str
    instructions: (str | Callable[[RunContextWrapper[TContext], Agent[TContext]], MaybeAwaitable[str]]) | None = None
    handoff_description: str | None = None
    handoffs: list[Agent[Any] | Handoff[TContext]] = field(default_factory=list)
    model: str | Model | None = None
    model_settings: ModelSettings = field(default_factory=ModelSettings)
    tools: list[Tool] = field(default_factory=list)
    input_guardrails: list[InputGuardrail[TContext]] = field(default_factory=list)
    output_guardrails: list[OutputGuardrail[TContext]] = field(default_factory=list)
    output_type: type[Any] | None = None
    hooks: AgentHooks[TContext] | None = None
    tool_use_behavior: (Literal["run_llm_again", "stop_on_first_tool"] | StopAtTools | ToolsToFinalOutputFunction) = "run_llm_again"

    def clone(self, **kwargs: Any) -> Agent[TContext]:
        return dataclasses.replace(self, **kwargs)

class StopAtTools(TypedDict):
    stop_at_tool_names: list[str]

@dataclass
class ToolsToFinalOutputResult:
    is_final_output: bool
    final_output: Any | None = None

ToolsToFinalOutputFunction: TypeAlias = Callable[[RunContextWrapper[TContext], list[FunctionToolResult]], MaybeAwaitable[ToolsToFinalOutputResult]]
