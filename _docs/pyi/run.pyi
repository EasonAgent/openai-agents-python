import abc
import asyncio
from dataclasses import dataclass, field
from collections.abc import AsyncIterator
from typing import Any, Generic, Literal, Union
from typing_extensions import TypeVar, TypeAlias

from openai.types.responses import ResponseFunctionToolCall, ResponseComputerToolCall

from .agent import Agent, ToolsToFinalOutputResult
from .models import Usage, ModelProvider, OpenAIProvider, ModelSettings, Model, ModelResponse
from .tracing import Span
from .items import TResponse, TResponseInputItem, TResponseOutputItem, TResponseStreamEvent, AgentOutputSchema
from .guardrail import InputGuardrail, OutputGuardrail, InputGuardrailResult, OutputGuardrailResult
from .lifecycle import RunHooks
from .tool import Handoff, FunctionTool, ComputerTool, HandoffInputFilter, FunctionToolResult

# --------------------------------------------------------------------------------
# run_context
# --------------------------------------------------------------------------------
# src/agents/run_context.py
TContext = TypeVar("TContext", default=Any)

@dataclass
class RunContextWrapper(Generic[TContext]):
    context: TContext
    usage: Usage = field(default_factory=Usage)


""" --------------------------------------------------------------------------------------------------------------------
Runner: 整体运行入口
    非流式: (调用关系) run(...) -> RunResult
        _run_single_turn(...) -> SingleStepResult -- 单步
        _get_new_response(...) -> ModelResponse -- 调用模型 Model.get_response()
    流式: (调用关系) run_streamed(...) -> RunResultStreaming
        _run_streamed_impl(...) -> None -- 调用 RunImpl
        _run_single_turn_streamed(...) -> SingleStepResult
    共用:
        _get_single_step_result_from_response: 调用 RunImpl.process_model_response() 和 RunImpl.execute_tools_and_side_effects(), 得到 SingleStepResult
-------------------------------------------------------------------------------------------------------------------- """
class Runner:
    @classmethod
    async def run(cls, starting_agent: Agent[TContext], input: str | list[TResponseInputItem], *, context: TContext | None = None, max_turns: int = DEFAULT_MAX_TURNS, hooks: RunHooks[TContext] | None = None, run_config: RunConfig | None = None) -> RunResult: ...
    @classmethod
    def run_sync(cls, starting_agent: Agent[TContext], input: str | list[TResponseInputItem], *, context: TContext | None = None, max_turns: int = DEFAULT_MAX_TURNS, hooks: RunHooks[TContext] | None = None, run_config: RunConfig | None = None) -> RunResult: ...
    @classmethod
    def run_streamed(cls, starting_agent: Agent[TContext], input: str | list[TResponseInputItem], *, context: TContext | None = None, max_turns: int = DEFAULT_MAX_TURNS, hooks: RunHooks[TContext] | None = None, run_config: RunConfig | None = None) -> RunResultStreaming: ...

    # 非流式
    @classmethod 
    async def _run_single_turn(cls, *, agent: Agent[Any], original_input: str | list[TResponseInputItem], generated_items: list[RunItem], hooks: RunHooks[TContext], context_wraper: RunContextWrapper[TContext], run_config: RunConfig, should_run_agent_start_hooks: bool) -> SingleStepResult: ...
    @classmethod 
    async def _run_input_guardrails(cls, agent: Agent[Any], guardrails: list[InputGuardrail[TContext]], input: str | list[TResponseInputItem], context: RunContextWrapper[TContext]) -> list[InputGuardrailResult]: ...
    @classmethod # 调用 Model.get_response()
    async def _get_new_response(cls, agent: Agent[TContext], system_prompt: str | None, input: list[TResponseInputItem], output_schema: AgentOutputSchema | None, handoffs: list[Handoff], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> ModelResponse: ...

    # 流式
    @classmethod # 调用 RunImpl.stream_step_result_to_queue(single_step_result, streamed_result._event_queue)
    async def _run_single_turn_streamed(cls, streamed_result: RunResultStreaming, agent: Agent[TContext], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig, should_run_agent_start_hooks: bool) -> SingleStepResult: ...
    @classmethod # 并发调用 RunImpl.run_single_input_guardrail(agent, guardrail, input, context)
    async def _run_input_guardrails_with_queue(cls, agent: Agent[Any], guardrails: list[InputGuardrail[TContext]], input: str | list[TResponseInputItem], context: RunContextWrapper[TContext], streamed_result: RunResultStreaming, parent_span: Span[Any]): ...
    @classmethod
    async def _run_streamed_impl(cls, starting_input: str | list[TResponseInputItem], streamed_result: RunResultStreaming, starting_agent: Agent[TContext], max_turns: int, hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig): ...

    # 下面是流式/非流式共用的
    @classmethod # 并发调用 RunImpl.run_single_output_guardrail(guardrail, agent, agent_output, context)
    async def _run_output_guardrails(cls, guardrails: list[OutputGuardrail[TContext]], agent: Agent[TContext], agent_output: Any, context: RunContextWrapper[TContext]) -> list[OutputGuardrailResult]: ...
    @classmethod # 调用 RunImpl.process_model_response() 和 RunImpl.execute_tools_and_side_effects(), 得到 SingleStepResult
    async def _get_single_step_result_from_response(cls, *, agent: Agent[TContext], original_input: str | list[TResponseInputItem], pre_step_items: list[RunItem], new_response: ModelResponse, output_schema: AgentOutputSchema | None, handoffs: list[Handoff], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> SingleStepResult: ...
    @classmethod
    def _get_output_schema(cls, agent: Agent[Any]) -> AgentOutputSchema | None: ...
    @classmethod
    def _get_handoffs(cls, agent: Agent[Any]) -> list[Handoff]: ...
    @classmethod
    def _get_model(cls, agent: Agent[Any], run_config: RunConfig) -> Model: ...


# --------------------------------------------------------------------------------
# RunResult
# --------------------------------------------------------------------------------
T = TypeVar("T")

@dataclass
class RunResultBase(abc.ABC):
    input: str | list[TResponseInputItem]
    new_items: list[RunItem]
    raw_responses: list[ModelResponse]
    final_output: Any
    input_guardrail_results: list[InputGuardrailResult]
    output_guardrail_results: list[OutputGuardrailResult]
    @property
    def last_agent(self) -> Agent[Any]: ...
    def final_output_as(self, cls: type[T], raise_if_incorrect_type: bool = False) -> T: ...
    def to_input_list(self) -> list[TResponseInputItem]: ...

@dataclass
class RunResult(RunResultBase):
    @property
    def last_agent(self) -> Agent[Any]: ...
@dataclass
class RunResultStreaming(RunResultBase):
    current_agent: Agent[Any]
    current_turn: int
    max_turns: int
    final_output: Any
    is_complete: bool = False
    @property
    def last_agent(self) -> Agent[Any]: ...
    async def stream_events(self) -> AsyncIterator[StreamEvent]: ...


# --------------------------------------------------------------------------------
# StepResult: 建模run过程中一步. 
#   next_step: 包括 handoff, final output, run again
# --------------------------------------------------------------------------------
@dataclass
class SingleStepResult:
    original_input: str | list[TResponseInputItem]
    model_response: ModelResponse
    pre_step_items: list[RunItem]
    new_step_items: list[RunItem]
    next_step: NextStepHandoff | NextStepFinalOutput | NextStepRunAgain
    @property
    def generated_items(self) -> list[RunItem]: ...

@dataclass
class NextStepHandoff:
    new_agent: Agent[Any]
@dataclass
class NextStepFinalOutput:
    output: Any
@dataclass
class NextStepRunAgain:
    pass


# --------------------------------------------------------------------------------
# RunConfig
# --------------------------------------------------------------------------------
DEFAULT_MAX_TURNS = 10


@dataclass
class RunConfig:
    model: str | Model | None = None
    model_provider: ModelProvider = field(default_factory=OpenAIProvider)
    model_settings: ModelSettings | None = None
    handoff_input_filter: HandoffInputFilter | None = None
    input_guardrails: list[InputGuardrail[Any]] | None = None
    output_guardrails: list[OutputGuardrail[Any]] | None = None
    tracing_disabled: bool = False
    trace_include_sensitive_data: bool = True
    workflow_name: str = "Agent workflow"
    trace_id: str | None = None
    group_id: str | None = None
    trace_metadata: dict[str, Any] | None = None

""" --------------------------------------------------------------------------------------------------------------------
RunImpl: 运行实现
    顶层接口:
        execute_tools_and_side_effects(...) -> SingleStepResult 执行工具
            execute_function_tool_calls | execute_computer_actions | execute_handoffs
        run_single_input_guardrail(...) -> InputGuardrailResult
        run_single_output_guardrail(...) -> OutputGuardrailResult
    辅助函数:
        process_model_response(agent, response, output_schema, handoffs) -> ProcessedResponse. 转为 RunImpl 执行过程的中间数据 (用于 execute_tools_and_side_effects)
-------------------------------------------------------------------------------------------------------------------- """
class RunImpl:
    @classmethod # 会调用 cls.execute_function_tool_calls | cls.execute_computer_actions | cls.execute_handoffs
    async def execute_tools_and_side_effects(cls, *, agent: Agent[TContext], original_input: str | list[TResponseInputItem], pre_step_items: list[RunItem], new_response: ModelResponse, processed_response: ProcessedResponse, output_schema: AgentOutputSchema | None, hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> SingleStepResult: ...
    @classmethod
    def process_model_response(cls, *, agent: Agent[Any], response: ModelResponse, output_schema: AgentOutputSchema | None, handoffs: list[Handoff]) -> ProcessedResponse: ...
    
    @classmethod
    async def execute_function_tool_calls(cls, *, agent: Agent[TContext], tool_runs: list[ToolRunFunction], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], config: RunConfig) -> list[FunctionToolResult]: ...
    @classmethod
    async def execute_computer_actions(cls, *, agent: Agent[TContext], actions: list[ToolRunComputerAction], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], config: RunConfig) -> list[RunItem]: ...
    @classmethod
    async def execute_handoffs(cls, *, agent: Agent[TContext], original_input: str | list[TResponseInputItem], pre_step_items: list[RunItem], new_step_items: list[RunItem], new_response: ModelResponse, run_handoffs: list[ToolRunHandoff], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> SingleStepResult: ...
    @classmethod # -> cls.run_final_output_hooks
    async def execute_final_output(cls, *, agent: Agent[TContext], original_input: str | list[TResponseInputItem], new_response: ModelResponse, pre_step_items: list[RunItem], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> SingleStepResult: ...
    @classmethod
    async def run_final_output_hooks(cls, agent: Agent[TContext], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], final_output: Any): ...
    
    @classmethod
    async def run_single_input_guardrail(cls, agent: Agent[Any], guardrail: InputGuardrail[TContext], input: str | list[TResponseInputItem], context: RunContextWrapper[TContext]) -> InputGuardrailResult: ...
    @classmethod
    async def run_single_output_guardrail(cls, guardrail: OutputGuardrail[TContext], agent: Agent[Any], agent_output: Any, context: RunContextWrapper[TContext]) -> OutputGuardrailResult: ...

    @classmethod # 将流式的一个 step result 中的信息放到 queue 中
    def stream_step_result_to_queue(cls, step_result: SingleStepResult, queue: asyncio.Queue[StreamEvent | QueueCompleteSentinel]): ...
    @classmethod
    async def _check_for_final_output_from_tools(cls, *, agent: Agent[TContext], tool_results: list[FunctionToolResult], context_wrapper: RunContextWrapper[TContext], config: RunConfig) -> ToolsToFinalOutputResult: ...


@dataclass
class ProcessedResponse:
    new_items: list[RunItem]
    handoffs: list[ToolRunHandoff]
    functions: list[ToolRunFunction]
    computer_actions: list[ToolRunComputerAction]
@dataclass
class ToolRunHandoff:
    handoff: Handoff
    tool_call: ResponseFunctionToolCall
@dataclass
class ToolRunFunction:
    tool_call: ResponseFunctionToolCall
    function_tool: FunctionTool
@dataclass
class ToolRunComputerAction:
    tool_call: ResponseComputerToolCall
    computer_tool: ComputerTool

class QueueCompleteSentinel: # 队列的空元素?
    pass



# --------------------------------------------------------------------------------
# StreamEvent: 对于 Runner/agent 流式行为的建模
# --------------------------------------------------------------------------------
from agents import StreamEvent, RunItem
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



