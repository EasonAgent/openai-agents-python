import abc
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, Literal, Union

from typing_extensions import TypeAlias, TypeVar

from .agent import Agent
from .items import RunItem, TResponseInputItem
from .run import RunContextWrapper, TContext

""" --------------------------------------------------------------------------------------------------------------------
Tool: 工具定义
    工具定义: name, description, params_json_schema
    工具调用: on_invoke_tool
    输入输出: 均为 str
-------------------------------------------------------------------------------------------------------------------- """
Tool = Union[FunctionTool, FileSearchTool, WebSearchTool, ComputerTool]

@dataclass
class FunctionTool:
    name: str
    description: str
    params_json_schema: dict[str, Any]
    on_invoke_tool: Callable[[RunContextWrapper[Any], str], Awaitable[Any]]
    strict_json_schema: bool = True

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
