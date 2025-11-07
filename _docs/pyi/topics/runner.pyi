import copy, asyncio
from typing import Unpack, Any

from ..run import TContext, RunResultBase, RunResult, RunResultStreaming, DEFAULT_MAX_TURNS, RunHooks, RunConfig, RunContextWrapper, RunOptions
from ..run_impl import RunImpl
from ..agent import Agent
from ..item import TResponseInputItem, AgentUpdatedStreamEvent, RawResponsesStreamEvent, RunItemStreamEvent, ItemHelpers


""" --------------------------------------------------------------------------------------------------------------------
上层调用: run_demo_loop
-------------------------------------------------------------------------------------------------------------------- """
async def run_demo_loop(agent: Agent[Any], *, stream: bool = True) -> None:
    """Run a simple REPL loop with the given agent.
    This utility allows quick manual testing and debugging of an agent from the
    command line. Conversation state is preserved across turns. Enter ``exit``
    or ``quit`` to stop the loop."""
    current_agent = agent
    input_items: list[TResponseInputItem] = []
    while True:
        user_input = input(" > ")
        if user_input.strip().lower() in {"exit", "quit"}:
            break
        input_items.append({"role": "user", "content": user_input})
        result: RunResultBase
        if stream:
            result = Runner.run_streamed(current_agent, input=input_items)
            async for event in result.stream_events():
                if isinstance(event, RawResponsesStreamEvent):
                    if isinstance(event.data, ResponseTextDeltaEvent):
                        print(event.data.delta, end="", flush=True)
                elif isinstance(event, RunItemStreamEvent):
                    if event.item.type == "tool_call_item":
                        print("\n[tool called]", flush=True)
                    elif event.item.type == "tool_call_output_item":
                        print(f"\n[tool output: {event.item.output}]", flush=True)
                    elif event.item.type == "message_output_item":
                        message = ItemHelpers.text_message_output(event.item)
                        print(message, end="", flush=True)
                elif isinstance(event, AgentUpdatedStreamEvent):
                    print(f"\n[Agent updated: {event.new_agent.name}]", flush=True)
        else:
            result = await Runner.run(current_agent, input_items)
        current_agent = result.last_agent
        input_items = result.to_input_list()

""" --------------------------------------------------------------------------------------------------------------------
Runner: 顶层封装, 分离实现类
-------------------------------------------------------------------------------------------------------------------- """
runner = AgentRunner()

class Runner:
    @classmethod
    def run_streamed(cls, starting_agent: Agent[TContext], input: str | list[TResponseInputItem], *, context: TContext | None = None, max_turns: int = DEFAULT_MAX_TURNS, hooks: RunHooks[TContext] | None = None, run_config: RunConfig | None = None) -> RunResultStreaming:
        return runner.run_streamed(...)
    @classmethod
    async def run(cls, starting_agent: Agent[TContext], input: str | list[TResponseInputItem], *, context: TContext | None = None, max_turns: int = DEFAULT_MAX_TURNS, hooks: RunHooks[TContext] | None = None, run_config: RunConfig | None = None) -> RunResult:
        ...

""" --------------------------------------------------------------------------------------------------------------------
run_streamed
    - 初始化 trace
    - context_wrapper
    - streamed_result: RunResultStreaming
    返回: RunResultStreaming
-------------------------------------------------------------------------------------------------------------------- """
class AgentRunner:
    def run_streamed(
        self,
        starting_agent: Agent[TContext],
        input: str | list[TResponseInputItem],
        **kwargs: Unpack[RunOptions[TContext]],
    ) -> RunResultStreaming:
        context = kwargs.get("context")
        max_turns = kwargs.get("max_turns", DEFAULT_MAX_TURNS)
        hooks = kwargs.get("hooks")
        run_config = kwargs.get("run_config")
        previous_response_id = kwargs.get("previous_response_id")

        new_trace = (...)
        output_schema = AgentRunner._get_output_schema(starting_agent)
        context_wrapper: RunContextWrapper[TContext] = RunContextWrapper(context=context)

        streamed_result = RunResultStreaming(input=copy.deepcopy(input), new_items=[], current_agent=starting_agent, raw_responses=[], final_output=None, is_complete=False, current_turn=0, max_turns=max_turns, input_guardrail_results=[], output_guardrail_results=[], _current_agent_output_schema=output_schema, trace=new_trace, context_wrapper=context_wrapper)
        streamed_result._run_impl_task = asyncio.create_task(
            self._start_streaming(...)
        )
        return streamed_result

    @classmethod
    async def _start_streaming(
        cls,
        starting_input: str | list[TResponseInputItem],
        streamed_result: RunResultStreaming,
        starting_agent: Agent[TContext],
        max_turns: int,
        hooks: RunHooks[TContext],
        context_wrapper: RunContextWrapper[TContext],
        run_config: RunConfig,
        previous_response_id: str | None,
    ):
        if streamed_result.trace:
            streamed_result.trace.start(mark_as_current=True)
        current_span: Span[AgentSpanData] | None = None
        current_agent = starting_agent
        current_turn = 0
        should_run_agent_start_hooks = True
        tool_use_tracker = AgentToolUseTracker()
        streamed_result._event_queue.put_nowait(AgentUpdatedStreamEvent(new_agent=current_agent))
        try:
            while True:
                if streamed_result.is_complete:
                    break
                all_tools = await cls._get_all_tools(current_agent, context_wrapper)
                # Start an agent span if we don't have one. This span is ended if the current
                # agent changes, or if the agent loop ends.
                if current_span is None:
                    current_span = agent_span(...)
                    current_span.start(mark_as_current=True)
                current_turn += 1
                streamed_result.current_turn = current_turn  # updated streamed_result!
                if current_turn == 1:
                    # Run the input guardrails in the background and put the results on the queue
                    streamed_result._input_guardrails_task = asyncio.create_task(
                        cls._run_input_guardrails_with_queue(...)
                    )
                try:
                    turn_result = await cls._run_single_turn_streamed(...)
                    should_run_agent_start_hooks = False
                    streamed_result.raw_responses = streamed_result.raw_responses + [turn_result.model_response]
                    streamed_result.input = turn_result.original_input
                    streamed_result.new_items = turn_result.generated_items
                except AgentsException as exc:
                    streamed_result.is_complete = True
                    streamed_result._event_queue.put_nowait(QueueCompleteSentinel())
                    exc.run_data = RunErrorDetails(...)
                    raise
                except Exception as e:
                    if current_span:
                        _error_tracing.attach_error_to_span(...)
                    ...
            streamed_result.is_complete = True
        finally:
            if current_span:
                current_span.finish(reset_current=True)
            if streamed_result.trace:
                streamed_result.trace.finish(reset_current=True)

    @classmethod
    async def _run_single_turn_streamed(
        cls,
        streamed_result: RunResultStreaming,
        agent: Agent[TContext],
        hooks: RunHooks[TContext],
        context_wrapper: RunContextWrapper[TContext],
        run_config: RunConfig,
        should_run_agent_start_hooks: bool,
        tool_use_tracker: AgentToolUseTracker,
        all_tools: list[Tool],
        previous_response_id: str | None,
    ) -> SingleStepResult:
        if should_run_agent_start_hooks:
            await asyncio.gather(
                hooks.on_agent_start(context_wrapper, agent),
                agent.hooks.on_start(context_wrapper, agent)
            )
        output_schema = cls._get_output_schema(agent)
        streamed_result.current_agent = agent
        streamed_result._current_agent_output_schema = output_schema
        handoffs = cls._get_handoffs(agent)
        model = cls._get_model(agent, run_config)
        input = ItemHelpers.input_to_new_input_list(streamed_result.input)
        input.extend([item.to_input_item() for item in streamed_result.new_items])  # add the new_items!

        # 1. Stream the output events
        async for event in model.stream_response(...):
            if isinstance(event, ResponseCompletedEvent):
                ...  # record usage
                final_response = ModelResponse(...)
            streamed_result._event_queue.put_nowait(RawResponsesStreamEvent(data=event))
        # 2. At this point, the streaming is complete for this turn of the agent loop.
        if not final_response:
            raise ModelBehaviorError("Model did not produce a final response!")
        # 3. Now, we can process the turn as we do in the non-streaming case
        single_step_result = await cls._get_single_step_result_from_response(...)
        RunImpl.stream_step_result_to_queue(single_step_result, streamed_result._event_queue)
        return single_step_result