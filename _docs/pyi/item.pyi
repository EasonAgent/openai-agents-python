import abc
from dataclasses import dataclass
from typing import Union, Literal, TypeVar, Any, Generic
from typing_extensions import TypeAlias

from openai.types.responses import ResponseInputItemParam
from openai.types.responses import ResponseComputerToolCall, ResponseFileSearchToolCall, ResponseFunctionWebSearch
from openai.types.responses.response_reasoning_item import ResponseReasoningItem
from openai.types.responses.response_input_item_param import ComputerCallOutput, FunctionCallOutput
from openai.types.responses import Response, ResponseInputItemParam, ResponseOutputItem, ResponseStreamEvent, ResponseOutputMessage, ResponseFunctionToolCall

TResponse = Response
TResponseInputItem = ResponseInputItemParam
TResponseOutputItem = ResponseOutputItem
TResponseStreamEvent = ResponseStreamEvent
T = TypeVar("T", bound=Union[TResponseOutputItem, TResponseInputItem])

from .agent import Agent
from .model import Usage

# --------------------------------------------------------------------------------
# StreamEvent: 对于 Runner/agent 流式行为的建模
# --------------------------------------------------------------------------------
StreamEvent: TypeAlias = Union[RawResponsesStreamEvent, RunItemStreamEvent, AgentUpdatedStreamEvent]
@dataclass
class RawResponsesStreamEvent:
    data: TResponseStreamEvent
    type: Literal["raw_response_event"] = "raw_response_event"
@dataclass
class RunItemStreamEvent:
    name: Literal["message_output_created", "handoff_requested", "handoff_occured", "tool_called", "tool_output", "reasoning_item_created"]
    item: RunItem
    type: Literal["run_item_stream_event"] = "run_item_stream_event"
@dataclass
class AgentUpdatedStreamEvent:
    new_agent: Agent[Any]
    type: Literal["agent_updated_stream_event"] = "agent_updated_stream_event"


# --------------------------------------------------------------------------------
# Item
# --------------------------------------------------------------------------------
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


@dataclass
class ModelResponse:
    output: list[TResponseOutputItem]
    usage: Usage
    response_id: str | None
    def to_input_items(self) -> list[TResponseInputItem]: ...


# --------------------------------------------------------------------------------
# 
# --------------------------------------------------------------------------------
class ItemHelpers:
    @classmethod
    def extract_last_content(cls, message: TResponseOutputItem) -> str:
        """Extracts the last text content or refusal from a message."""
    @classmethod
    def extract_last_text(cls, message: TResponseOutputItem) -> str | None:
        """Extracts the last text content from a message, if any. Ignores refusals."""
    @classmethod
    def input_to_new_input_list(cls, input: str | list[TResponseInputItem]) -> list[TResponseInputItem]:
        """Converts a string or list of input items into a list of input items."""
    @classmethod
    def text_message_outputs(cls, items: list[RunItem]) -> str:
        """Concatenates all the text content from a list of message output items."""
    @classmethod
    def text_message_output(cls, message: MessageOutputItem) -> str:
        """Extracts all the text content from a single message output item."""
    @classmethod
    def tool_call_output_item(cls, tool_call: ResponseFunctionToolCall, output: str) -> FunctionCallOutput:
        """Creates a tool call output item from a tool call and its output."""
