import abc
import copy
import logging
import asyncio
from dataclasses import dataclass, field
from typing import TypeVar, Awaitable, Union, Generic, Any, AsyncIterator, Callable, cast
from typing_extensions import Unpack, NotRequired

from .model import Model, ModelSettings, Usage, ModelProvider, OpenAIProvider
from .agent import Agent, AgentOutputSchemaBase
from .tool import Tool, Handoff, FunctionTool
from .tracing import AgentSpanData, get_current_trace, Span
from .item import TResponseInputItem, RunItem, ModelResponse, ItemHelpers, StreamEvent
from .run_impl import RunImpl, QueueCompleteSentinel

T = TypeVar("T")
MaybeAwaitable = Union[Awaitable[T], T]

logger = logging.getLogger("openai.agents")


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
DEFAULT_MAX_TURNS = 10
DEFAULT_AGENT_RUNNER: AgentRunner = None  # type: ignore
# the value is set at the end of the module

def set_default_agent_runner(runner: AgentRunner | None) -> None: ...
def get_default_agent_runner() -> AgentRunner: ...


class Runner:
    async def run(
        cls,
        starting_agent: Agent[TContext],
        input: str | list[TResponseInputItem],
        *,
        context: TContext | None = None,
        max_turns: int = DEFAULT_MAX_TURNS,
        hooks: RunHooks[TContext] | None = None,
        run_config: RunConfig | None = None,
        previous_response_id: str | None = None,
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
            previous_response_id: The ID of the previous response, if using OpenAI models via the
                Responses API, this allows you to skip passing in input from the previous turn.
        Returns:
            A run result containing all the inputs, guardrail results and the output of the last
            agent. Agents may perform handoffs, so we don't know the specific type of the output.
        """
        runner = DEFAULT_AGENT_RUNNER
        return await runner.run(...)

    @classmethod
    def run_sync(cls, starting_agent: Agent[TContext], input: str | list[TResponseInputItem], *, context: TContext | None = None, max_turns: int = DEFAULT_MAX_TURNS, hooks: RunHooks[TContext] | None = None, run_config: RunConfig | None = None) -> RunResult:
        """Run a workflow synchronously, starting at the given agent. Note that this just wraps the
        `run` method, so it will not work if there's already an event loop (e.g. inside an async
        function, or in a Jupyter notebook or async context like FastAPI). For those cases, use
        the `run` method instead."""

    @classmethod
    def run_streamed(cls, starting_agent: Agent[TContext], input: str | list[TResponseInputItem], *, context: TContext | None = None, max_turns: int = DEFAULT_MAX_TURNS, hooks: RunHooks[TContext] | None = None, run_config: RunConfig | None = None) -> RunResultStreaming:
        """Run a workflow starting at the given agent in streaming mode. The returned result object
        contains a method you can use to stream semantic events as they are generated."""

class RunOptions(TypedDict, Generic[TContext]):
    context: NotRequired[TContext | None]
    max_turns: NotRequired[int]
    hooks: NotRequired[RunHooks[TContext] | None]
    run_config: NotRequired[RunConfig | None]
    previous_response_id: NotRequired[str | None]



class AgentRunner:
    async def run(
        self,
        starting_agent: Agent[TContext],
        input: str | list[TResponseInputItem],
        **kwargs: Unpack[RunOptions[TContext]],
    ) -> RunResult:
        context = kwargs.get("context")
        max_turns = kwargs.get("max_turns", DEFAULT_MAX_TURNS)
        hooks = kwargs.get("hooks")
        run_config = kwargs.get("run_config")
        previous_response_id = kwargs.get("previous_response_id")
        
        tool_use_tracker = AgentToolUseTracker()

        # TraceCtxManager
        with TraceCtxManager(...):
            current_turn = 0
            original_input: str | list[TResponseInputItem] = copy.deepcopy(input)
            generated_items: list[RunItem] = []       # 增量的结果
            model_responses: list[ModelResponse] = [] # 
            context_wrapper: RunContextWrapper[TContext] = RunContextWrapper(context=context)

            current_span: Span[AgentSpanData] | None = None # 处理不同 agents
            current_agent = starting_agent
            should_run_agent_start_hooks = True # 在进入span的时候触发

            try:
                while True:
                    all_tools = await AgentRunner._get_all_tools(current_agent, context_wrapper)
                    # Start an agent span if we don't have one. This span is ended if the current
                    # agent changes, or if the agent loop ends.
                    if current_span is None:
                        ...
                    current_turn += 1
                    if current_turn > max_turns:
                        ... # will raise MaxTurnsExceeded!
                    
                    logger.debug(f"Running agent {current_agent.name} (turn {current_turn})")
                    if current_turn == 1:
                        self._run_input_guardrails(...) # 在第一轮还会走 _run_input_guardrails
                        turn_result = await self._run_single_turn(...)  # 同下
                    else:
                        turn_result = await self._run_single_turn(
                            agent=current_agent,
                            original_input=original_input,
                            generated_items=generated_items,
                            hooks=hooks,
                            context_wrapper=context_wrapper,
                            run_config=run_config,
                            should_run_agent_start_hooks=should_run_agent_start_hooks,
                        )
                    should_run_agent_start_hooks = False

                    model_responses.append(turn_result.model_response)
                    original_input = turn_result.original_input
                    generated_items = turn_result.generated_items

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
            except AgentsException as exc:
                exc.run_data = RunErrorDetails(...)
                raise
            finally:
                if current_span:
                    current_span.finish(reset_current=True)

    @classmethod
    async def _run_single_turn(cls, *, agent: Agent[Any], original_input: str | list[TResponseInputItem], generated_items: list[RunItem], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig, should_run_agent_start_hooks: bool) -> SingleStepResult:
        # Ensure we run the hooks before anything else
        if should_run_agent_start_hooks:
            ...
        system_prompt = await agent.get_system_prompt(context_wrapper)
        output_schema = cls._get_output_schema(agent)
        handoffs = cls._get_handoffs(agent)
        input = ItemHelpers.input_to_new_input_list(original_input)
        input.extend([generated_item.to_input_item() for generated_item in generated_items])

        new_response = await cls._get_new_response(...) # see 模型调用
        return await cls._get_single_step_result_from_response(...)
    @classmethod 
    async def _run_input_guardrails(cls, agent: Agent[Any], guardrails: list[InputGuardrail[TContext]], input: str | list[TResponseInputItem], context: RunContextWrapper[TContext]) -> list[InputGuardrailResult]: ...
    @classmethod # 调用 Model.get_response()
    async def _get_new_response(cls, agent: Agent[TContext], system_prompt: str | None, input: list[TResponseInputItem], output_schema: AgentOutputSchemaBase | None, handoffs: list[Handoff], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> ModelResponse:
        model = cls._get_model(agent, run_config)
        model_settings = agent.model_settings.resolve(run_config.model_settings)
        new_response = await model.get_response(
            system_instructions=system_prompt,
            input=input,
            model_settings=model_settings,
            tools=agent.tools,
            output_schema=output_schema,
            handoffs=handoffs,
            tracing=get_model_tracing_impl(
                run_config.tracing_disabled, run_config.trace_include_sensitive_data
            ),
        )
        context_wrapper.usage.add(new_response.usage)
        return new_response



    @classmethod
    async def _run_input_guardrails_with_queue(cls, agent: Agent[Any], guardrails: list[InputGuardrail[TContext]], input: str | list[TResponseInputItem], context: RunContextWrapper[TContext], streamed_result: RunResultStreaming, parent_span: Span[Any]): 
        """ 并发调用 RunImpl.run_single_input_guardrail(agent, guardrail, input, context) """
        queue = streamed_result._input_guardrail_queue
        guardrail_tasks = [
            asyncio.create_task(RunImpl.run_single_input_guardrail(agent, guardrail, input, context))
            for guardrail in guardrails
        ]
        guardrail_results = []
        try:
            for done in asyncio.as_completed(guardrail_tasks):
                result = await done
                # ... put result to queue & guardrail_results
        except Exception:
            raise
        streamed_result.input_guardrail_results = guardrail_results
        
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
    async def _get_all_tools(cls, agent: Agent[Any], context_wrapper: RunContextWrapper[Any]) -> list[Tool]:
        return await agent.get_all_tools(context_wrapper)
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
    @property
    def last_response_id(self) -> str | None: ...

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
    trace: Trace | None = field(repr=False)
    is_complete: bool = False

    # Queues that the background run_loop writes to
    _event_queue: asyncio.Queue[StreamEvent | QueueCompleteSentinel] = field(default_factory=asyncio.Queue, repr=False)
    _input_guardrail_queue: asyncio.Queue[InputGuardrailResult] = field(default_factory=asyncio.Queue, repr=False)
    # Store the asyncio tasks that we're waiting on
    _run_impl_task: asyncio.Task[Any] | None = field(default=None, repr=False)
    _input_guardrails_task: asyncio.Task[Any] | None = field(default=None, repr=False)
    _output_guardrails_task: asyncio.Task[Any] | None = field(default=None, repr=False)
    _stored_exception: Exception | None = field(default=None, repr=False)

    def cancel(self) -> None:
        """Cancels the streaming run, stopping all background tasks and marking the run as completed."""
    @property
    def last_agent(self) -> Agent[Any]: ...
    async def stream_events(self) -> AsyncIterator[StreamEvent]:
        """Stream deltas for new items as they are generated. We're using the types from the
        OpenAI Responses API, so these are semantic events: each event has a `type` field that
        describes the type of the event, along with the data for that event.
        This will raise:
        - A MaxTurnsExceeded exception if the agent exceeds the max_turns limit.
        - A GuardrailTripwireTriggered exception if a guardrail is tripped.
        """


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
