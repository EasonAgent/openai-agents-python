from dataclasses import dataclass
import abc
from typing import Union, Any, Generic, Literal
from typing_extensions import TypeVar, TypeAlias

from pydantic import TypeAdapter
from openai.types.responses import (
    Response, ResponseInputItemParam, ResponseOutputItem, ResponseStreamEvent, ResponseOutputMessage, ResponseFunctionToolCall,
    ResponseComputerToolCall, ResponseFileSearchToolCall, ResponseFunctionWebSearch
)
from openai.types.responses.response_input_item_param import ComputerCallOutput, FunctionCallOutput
from openai.types.responses.response_reasoning_item import ResponseReasoningItem

from .agent import Agent
""" --------------------------------------------------------------------------------------------------------------------
Items: 定义运行时的输入输出数据类型
-------------------------------------------------------------------------------------------------------------------- """
TResponse = Response
"""A type alias for the Response type from the OpenAI SDK."""
TResponseInputItem = ResponseInputItemParam
"""A type alias for the ResponseInputItemParam type from the OpenAI SDK."""
TResponseOutputItem = ResponseOutputItem
"""A type alias for the ResponseOutputItem type from the OpenAI SDK."""
TResponseStreamEvent = ResponseStreamEvent
"""A type alias for the ResponseOutputItem type from the OpenAI SDK."""

T = TypeVar("T", bound=Union[TResponseOutputItem, TResponseInputItem])
@dataclass
class RunItemBase(Generic[T], abc.ABC):
    agent: Agent[Any]
    raw_item: T
    def to_input_item(self) -> TResponseInputItem: ...

@dataclass
class MessageOutputItem(RunItemBase[ResponseOutputMessage]):
    raw_item: ResponseOutputMessage
    type: Literal["message_output_item"] = "message_output_item"
@dataclass
class HandoffCallItem(RunItemBase[ResponseFunctionToolCall]):
    raw_item: ResponseFunctionToolCall
    type: Literal["handoff_call_item"] = "handoff_call_item"
@dataclass
class HandoffOutputItem(RunItemBase[TResponseInputItem]):
    raw_item: TResponseInputItem
    source_agent: Agent[Any]
    target_agent: Agent[Any]
    type: Literal["handoff_output_item"] = "handoff_output_item"

ToolCallItemTypes: TypeAlias = Union[ResponseFunctionToolCall, ResponseComputerToolCall, ResponseFileSearchToolCall, ResponseFunctionWebSearch]
@dataclass
class ToolCallItem(RunItemBase[ToolCallItemTypes]):
    raw_item: ToolCallItemTypes
    type: Literal["tool_call_item"] = "tool_call_item"
@dataclass
class ToolCallOutputItem(RunItemBase[Union[FunctionCallOutput, ComputerCallOutput]]):
    raw_item: FunctionCallOutput | ComputerCallOutput
    output: Any
    type: Literal["tool_call_output_item"] = "tool_call_output_item"
@dataclass
class ReasoningItem(RunItemBase[ResponseReasoningItem]):
    raw_item: ResponseReasoningItem
    type: Literal["reasoning_item"] = "reasoning_item"

RunItem: TypeAlias = Union[MessageOutputItem, HandoffCallItem, HandoffOutputItem, ToolCallItem, ToolCallOutputItem, ReasoningItem]


""" --------------------------------------------------------------------------------------------------------------------
AgentOutputSchema
-------------------------------------------------------------------------------------------------------------------- """
# src/agents/agent_output.py
@dataclass(init=False)
class AgentOutputSchema:
    _type_adapter: TypeAdapter[Any]
    _is_wrapped: bool
    _output_schema: dict[str, Any]
    strict_json_schema: bool
    def __init__(self, output_type: type[Any], strict_json_schema: bool = True): ...
    def is_plain_text(self) -> bool: ...
    def json_schema(self) -> dict[str, Any]: ...
    def validate_json(self, json_str: str, partial: bool = False) -> Any: ...
    def output_type_name(self) -> str: ...