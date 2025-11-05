import abc
import enum
from typing import Literal
from dataclasses import dataclass
from collections.abc import AsyncIterator

from .items import TResponseInputItem, TResponseOutputItem, TResponseStreamEvent, AgentOutputSchema
from .tool import Tool, Handoff
""" --------------------------------------------------------------------------------------------------------------------
Model: agents 场景下抽象 responses API

输入: SP, 增量的input
输出:
    非流式: ModelResponse, 同 responses API (ResponseOutputItem)
    流式: 同 responses API (ResponseStreamEvent)
-------------------------------------------------------------------------------------------------------------------- """
class Model(abc.ABC):
    @abc.abstractmethod
    async def get_response(self, system_instructions: str | None, input: str | list[TResponseInputItem], model_settings: ModelSettings, tools: list[Tool], output_schema: AgentOutputSchema | None, handoffs: list[Handoff], tracing: ModelTracing) -> ModelResponse: ...
    @abc.abstractmethod
    def stream_response(self, system_instructions: str | None, input: str | list[TResponseInputItem], model_settings: ModelSettings, tools: list[Tool], output_schema: AgentOutputSchema | None, handoffs: list[Handoff], tracing: ModelTracing) -> AsyncIterator[TResponseStreamEvent]: ...
# 对于两类API的实现
class OpenAIChatCompletionsModel(Model): ...
class OpenAIResponsesModel(Model): ...


@dataclass
class ModelResponse:
    output: list[TResponseOutputItem]
    usage: Usage
    referenceable_id: str | None
    def to_input_items(self) -> list[TResponseInputItem]: ...

# 提供模型
class ModelProvider(abc.ABC):
    @abc.abstractmethod
    def get_model(self, model_name: str | None) -> Model: ...
class OpenAIProvider(ModelProvider): ...


@dataclass
class ModelSettings:
    temperature: float | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    tool_choice: Literal["auto", "required", "none"] | str | None = None
    parallel_tool_calls: bool | None = False
    truncation: Literal["auto", "disabled"] | None = None
    max_tokens: int | None = None
    def resolve(self, override: ModelSettings | None) -> ModelSettings: ...


class ModelTracing(enum.Enum):
    DISABLED = 0
    ENABLED = 1
    ENABLED_WITHOUT_DATA = 2
    def is_disabled(self) -> bool: ...
    def include_data(self) -> bool: ...

@dataclass
class Usage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    def add(self, other: "Usage") -> None: ...
