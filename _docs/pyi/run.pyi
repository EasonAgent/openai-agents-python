import abc
from dataclasses import dataclass, field
from typing import TypeVar, Awaitable, Union, Generic, Any, AsyncIterator, Callable
import copy

from openai.types.responses import ResponseFunctionToolCall

from .model import Model, ModelSettings, Usage, ModelProvider, OpenAIProvider
from .agent import Agent, AgentOutputSchemaBase
from .tool import Tool, Handoff, FunctionTool
from .tracing import AgentSpanData, get_current_trace, Span
from .item import TResponseInputItem, RunItem

DEFAULT_MAX_TURNS = 10
T = TypeVar("T")
MaybeAwaitable = Union[Awaitable[T], T]

""" --------------------------------------------------------------------------------------------------------------------
RunContext: 运行时数据

# src/agents/run_context.py
-------------------------------------------------------------------------------------------------------------------- """
TContext = TypeVar("TContext", default=Any)

@dataclass
class RunContextWrapper(Generic[TContext]):
    context: TContext
    usage: Usage = field(default_factory=Usage)


# 相较于 AgentHooks, 仅仅 on_handoff 参数多了 from_agent 和 to_agent
class RunHooks(Generic[TContext]):
    async def on_agent_start(self, context: RunContextWrapper[TContext], agent: Agent[TContext]) -> None: ...
    async def on_agent_end(self, context: RunContextWrapper[TContext], agent: Agent[TContext], output: Any) -> None: ...
    async def on_handoff(self, context: RunContextWrapper[TContext], agent: Agent[TContext], from_agent: Agent[TContext], to_agent: Agent[TContext]) -> None: ...
    async def on_tool_start(self, context: RunContextWrapper[TContext], agent: Agent[TContext], tool: Tool) -> None: ...
    async def on_tool_end(self, context: RunContextWrapper[TContext], agent: Agent[TContext], tool: Tool, result: str) -> None: ...


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
    async def run(
        cls,
        starting_agent: Agent[TContext],
        input: str | list[TResponseInputItem],
        *,
        context: TContext | None = None,
        max_turns: int = DEFAULT_MAX_TURNS,
        hooks: RunHooks[TContext] | None = None,
        run_config: RunConfig | None = None,
    ) -> RunResult:
        """Run a workflow starting at the given agent. The agent will run in a loop until a final
        output is generated. The loop runs like so:
        1. The agent is invoked with the given input.
        2. If there is a final output (i.e. the agent produces something of type
            `agent.output_type`, the loop terminates.
        3. If there's a handoff, we run the loop again, with the new agent.
        4. Else, we run tool calls (if any), and re-run the loop.

        In two cases, the agent may raise an exception:
        1. If the max_turns is exceeded, a MaxTurnsExceeded exception is raised.
        2. If a guardrail tripwire is triggered, a GuardrailTripwireTriggered exception is raised.

        Note that only the first agent's input guardrails are run.

        Args:
            starting_agent: The starting agent to run.
            input: The initial input to the agent. You can pass a single string for a user message,
                or a list of input items.
            context: The context to run the agent with.
            max_turns: The maximum number of turns to run the agent for. A turn is defined as one
                AI invocation (including any tool calls that might occur).
            hooks: An object that receives callbacks on various lifecycle events.
            run_config: Global settings for the entire agent run.

        Returns:
            A run result containing all the inputs, guardrail results and the output of the last
            agent. Agents may perform handoffs, so we don't know the specific type of the output.
        """
        if hooks is None:
            hooks = RunHooks[Any]()
        if run_config is None:
            run_config = RunConfig()
        
        # TraceCtxManager
        with TraceCtxManager(...):
            current_turn = 0      # 轮次计数
            original_input: str | list[TResponseInputItem] = copy.deepcopy(input)
            generated_items: list[RunItem] = []       # 增量的结果
            model_responses: list[ModelResponse] = [] # 

            current_span: Span[AgentSpanData] | None = None # 处理不同 agents
            current_agent = starting_agent
            should_run_agent_start_hooks = True # 在进入span的时候触发

            try:
                while True:
                    # 准备 span
                    if current_span is None:
                        ...
                    # 轮次计数
                    current_turn += 1
                    if current_turn > max_turns:
                        ...
                    
                    # 正式进入! 
                    logger.debug(
                        f"Running agent {current_agent.name} (turn {current_turn})",
                    )
                    if current_turn == 1:
                        ... # 在第一轮还会走 _run_input_guardrails
                    else:
                        turn_result = await cls._run_single_turn(
                            agent=current_agent,
                            original_input=original_input,
                            generated_items=generated_items,
                            hooks=hooks,
                            context_wrapper=context_wrapper,
                            run_config=run_config,
                            should_run_agent_start_hooks=should_run_agent_start_hooks,
                        )
                    should_run_agent_start_hooks = False

                    # 存储需要返回的信息
                    model_responses.append(turn_result.model_response)
                    original_input = turn_result.original_input
                    generated_items = turn_result.generated_items

                    # 逻辑判断!
                    if isinstance(turn_result.next_step, NextStepFinalOutput):
                        return RunResult(
                            input=original_input,
                            new_items=generated_items,
                            raw_responses=model_responses,
                            final_output=turn_result.next_step.output,
                            _last_agent=current_agent,
                            input_guardrail_results=input_guardrail_results,
                            output_guardrail_results=output_guardrail_results,
                        )
                    elif isinstance(turn_result.next_step, NextStepHandoff):
                        current_agent = cast(Agent[TContext], turn_result.next_step.new_agent)
                        current_span.finish(reset_current=True)
                        current_span = None
                        should_run_agent_start_hooks = True
                    elif isinstance(turn_result.next_step, NextStepRunAgain):
                        pass
            finally:
                if current_span:
                    current_span.finish(reset_current=True)

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
    async def _get_new_response(cls, agent: Agent[TContext], system_prompt: str | None, input: list[TResponseInputItem], output_schema: AgentOutputSchemaBase | None, handoffs: list[Handoff], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> ModelResponse: ...


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
    async def _get_single_step_result_from_response(cls, *, agent: Agent[TContext], original_input: str | list[TResponseInputItem], pre_step_items: list[RunItem], new_response: ModelResponse, output_schema: AgentOutputSchemaBase | None, handoffs: list[Handoff], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> SingleStepResult: ...
    @classmethod
    def _get_output_schema(cls, agent: Agent[Any]) -> AgentOutputSchemaBase | None: ...
    @classmethod
    def _get_handoffs(cls, agent: Agent[Any]) -> list[Handoff]: ...
    @classmethod
    def _get_model(cls, agent: Agent[Any], run_config: RunConfig) -> Model: ...

# --------------------------------------------------------------------------------
# RunConfig
# --------------------------------------------------------------------------------
@dataclass
class RunConfig:
    """Configures settings for the entire agent run."""
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

# --------------------------------------------------------------------------------
# RunResult
# --------------------------------------------------------------------------------
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
    async def execute_tools_and_side_effects(cls, *, agent: Agent[TContext], original_input: str | list[TResponseInputItem], pre_step_items: list[RunItem], new_response: ModelResponse, processed_response: ProcessedResponse, output_schema: AgentOutputSchemaBase | None, hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> SingleStepResult: ...
    @classmethod
    def process_model_response(cls, *, agent: Agent[Any], response: ModelResponse, output_schema: AgentOutputSchemaBase | None, handoffs: list[Handoff]) -> ProcessedResponse: ...
    
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



class TraceCtxManager:
    """Creates a trace only if there is no current trace, and manages the trace lifecycle."""
    def __enter__(self) -> TraceCtxManager:
        current_trace = get_current_trace()
        if not current_trace:
            self.trace.start(mark_as_current=True)
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.trace.finish(reset_current=True)


# --------------------------------------------------------------------------------
# Guardrail: 
# --------------------------------------------------------------------------------
@dataclass
class InputGuardrail(Generic[TContext]):
    guardrail_function: Callable[[RunContextWrapper[TContext], Agent[Any], str | list[TResponseInputItem]], MaybeAwaitable[GuardrailFunctionOutput]]
    name: str | None = None
    def get_name(self) -> str: ...
    async def run(self, agent: Agent[Any], input: str | list[TResponseInputItem], context: RunContextWrapper[TContext]) -> InputGuardrailResult: ...

@dataclass
class OutputGuardrail(Generic[TContext]):
    guardrail_function: Callable[[RunContextWrapper[TContext], Agent[Any], Any], MaybeAwaitable[GuardrailFunctionOutput]]
    name: str | None = None
    def get_name(self) -> str: ...
    async def run(self, context: RunContextWrapper[TContext], agent: Agent[Any], agent_output: Any) -> OutputGuardrailResult: ...

@dataclass
class GuardrailFunctionOutput:
    output_info: Any
    tripwire_triggered: bool

@dataclass
class InputGuardrailResult:
    guardrail: InputGuardrail[Any]
    output: GuardrailFunctionOutput

@dataclass
class OutputGuardrailResult:
    guardrail: OutputGuardrail[Any]
    agent_output: Any
    agent: Agent[Any]
    output: GuardrailFunctionOutput
