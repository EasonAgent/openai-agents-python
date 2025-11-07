
## Streaming

1. **运行结果** (RunResultStreaming): `Runner.run_streamed() -> RunResultStreaming` 和非异步场景下的差异: 
    - 核心差异: 相较于 `Runner.run() -> RunResult`, 多了 `.stream_events()`
    - 数据侧设计:
        - 通过 `_run_impl_task, _input_guardrails_task, _output_guardrails_task: asyncio.Task[Any]` 来存储异步任务
        - 通过 `_event_queue: asyncio.Queue[StreamEvent | QueueCompleteSentinel]` 来存储输出事件队列
2. **事件流** (StreamEvent): 通过result的 `.stream_events()` gives you an async stream of StreamEvent objects
    1. `async def stream_events(self) -> AsyncIterator[StreamEvent]`
3. **事件类型**: StreamEvent 包括三种类型/粒度: `StreamEvent: TypeAlias = Union[RawResponsesStreamEvent, RunItemStreamEvent, AgentUpdatedStreamEvent]`
    1. `AgentUpdatedStreamEvent`: 粒度最大的, 新agent 
        1. `.type` = "agent_updated_stream_event"
        2. 数据: .new_agent
    2. `RunItemStreamEvent`: 新的 RunItem (.item)
        1. `.type` = "run_item_stream_event"
        2. `.name` 包括: 
            1. message_output_created
            2. handoff_requested
            3. handoff_occured
            4. tool_called
            5. tool_output
            6. reasoning_item_created
    3. `RawResponsesStreamEvent`: 新的 LLM 原始响应 (.data)
        1. `.type` = "raw_response_event"
        2. 数据: .data
4. (相较于responses) Chat 模型如何生成 Event? 参见 model 部分实现


### 处理案例

```python
# examples/basic/stream_items.py
result = Runner.run_streamed(...)

print("=== Run starting ===")
async for event in result.stream_events():  # 处理 .stream_events() 返回的 StreamEvent 流
    # We'll ignore the raw responses event deltas
    if event.type == "raw_response_event":
        continue
    # When the agent updates, print that
    elif event.type == "agent_updated_stream_event":
        print(f"Agent updated: {event.new_agent.name}")
        continue
    # When items are generated, print them
    elif event.type == "run_item_stream_event":
        if event.item.type == "tool_call_item":
            print("-- Tool was called")
        elif event.item.type == "tool_call_output_item":
            print(f"-- Tool output: {event.item.output}")
        elif event.item.type == "message_output_item":
            print(f"-- Message output:\n {ItemHelpers.text_message_output(event.item)}")
        else:
            pass  # Ignore other event types
print("=== Run complete ===")

""" 
=== Run starting ===
Agent updated: Joker
-- Tool was called
-- Tool output: 3
-- Message output: ...
=== Run complete ===
"""
```

### RunResultStreaming
- 封装流式运行的输出, 核心是 `stream_events() -> AsyncIterator[StreamEvent]` 方法
- 数据:
    - 通过 `_run_impl_task, _input_guardrails_task, _output_guardrails_task: asyncio.Task[Any]` 来存储异步任务
    - 通过 `_event_queue: asyncio.Queue[StreamEvent | QueueCompleteSentinel]` 来存储输出事件队列
- 辅助函数
    - `_check_errors`: 错误处理. 将exception保存到 `_stored_exception` 中 (延迟抛出)
        1. 检查 max_turns, 若触发, 抛出 MaxTurnsExceeded; 
        2. 检查输入guardrails队列, 若触发, 抛出 GuardrailTripwireTriggered
        3. 检查 _run_impl_task/_input_guardrails_task/_output_guardrails_task, 若触发, 抛出相应 Exception
    - `_cleanup_tasks`: 取消3个异步任务

```python
# src/agents/result.py
@dataclass
class RunResultStreaming(RunResultBase):
    """The result of an agent run in streaming mode. You can use the `stream_events` method to
    receive semantic events as they are generated.

    The streaming method will raise:
    - A MaxTurnsExceeded exception if the agent exceeds the max_turns limit.
    - A GuardrailTripwireTriggered exception if a guardrail is tripped.
    """
    is_complete: bool = False
    """Whether the agent has finished running."""

    # Queues that the background run_loop writes to
    _event_queue: asyncio.Queue[StreamEvent | QueueCompleteSentinel] = field(
        default_factory=asyncio.Queue, repr=False
    )
    _input_guardrail_queue: asyncio.Queue[InputGuardrailResult] = field(
        default_factory=asyncio.Queue, repr=False
    )

    # Store the asyncio tasks that we're waiting on
    _run_impl_task: asyncio.Task[Any] | None = field(default=None, repr=False) # 下面的三个队列存储, 在 Runner 中创建
    _input_guardrails_task: asyncio.Task[Any] | None = field(default=None, repr=False)
    _output_guardrails_task: asyncio.Task[Any] | None = field(default=None, repr=False)

    _stored_exception: Exception | None = field(default=None, repr=False)


    async def stream_events(self) -> AsyncIterator[StreamEvent]:
        """Stream deltas for new items as they are generated. We're using the types from the
        OpenAI Responses API, so these are semantic events: each event has a `type` field that
        describes the type of the event, along with the data for that event.

        This will raise:
        - A MaxTurnsExceeded exception if the agent exceeds the max_turns limit.
        - A GuardrailTripwireTriggered exception if a guardrail is tripped.
        """
        while True: # 循环逻辑: complete/exception 的时候break
            self._check_errors()
            if self._stored_exception:
                logger.debug("Breaking due to stored exception")
                self.is_complete = True
                break

            if self.is_complete and self._event_queue.empty():
                break

            try:
                item = await self._event_queue.get()
            except asyncio.CancelledError:
                break

            if isinstance(item, QueueCompleteSentinel):
                self._event_queue.task_done() # 结束队列! 
                # Check for errors, in case the queue was completed due to an exception
                self._check_errors()
                break

            yield item
            self._event_queue.task_done()

        if self._trace:
            self._trace.finish(reset_current=True)

        self._cleanup_tasks()

        if self._stored_exception:
            raise self._stored_exception
```

- _check_errors: 检查错误

```python
    def _check_errors(self):
        if self.current_turn > self.max_turns:
            self._stored_exception = MaxTurnsExceeded(f"Max turns ({self.max_turns}) exceeded")

        # Fetch all the completed guardrail results from the queue and raise if needed
        while not self._input_guardrail_queue.empty():
            guardrail_result = self._input_guardrail_queue.get_nowait()
            if guardrail_result.output.tripwire_triggered:
                self._stored_exception = InputGuardrailTripwireTriggered(guardrail_result)

        # Check the tasks for any exceptions
        if self._run_impl_task and self._run_impl_task.done():
            exc = self._run_impl_task.exception()
            if exc and isinstance(exc, Exception):
                self._stored_exception = exc
        if self._input_guardrails_task and self._input_guardrails_task.done(): # ...同
        if self._output_guardrails_task and self._output_guardrails_task.done(): # ...同
```

- _cleanup_tasks: 取消异步任务
```python
    def _cleanup_tasks(self):
        if self._run_impl_task and not self._run_impl_task.done():
            self._run_impl_task.cancel()

        if self._input_guardrails_task and not self._input_guardrails_task.done():
            self._input_guardrails_task.cancel()

        if self._output_guardrails_task and not self._output_guardrails_task.done():
            self._output_guardrails_task.cancel()
```



### StreamEvent
```python
# src/agents/stream_events.py
from .items import RunItem, TResponseStreamEvent

@dataclass
class RawResponsesStreamEvent:
    """Streaming event from the LLM. These are 'raw' events, i.e. they are directly passed through from the LLM. """

    data: TResponseStreamEvent
    """The raw responses streaming event from the LLM."""
    type: Literal["raw_response_event"] = "raw_response_event"

@dataclass
class RunItemStreamEvent:
    """Streaming events that wrap a `RunItem`. As the agent processes the LLM response, it will
    generate these events for new messages, tool calls, tool outputs, handoffs, etc.
    """
    name: Literal[
        "message_output_created",
        "handoff_requested",
        "handoff_occured",
        "tool_called",
        "tool_output",
        "reasoning_item_created",
    ]
    """The name of the event."""
    item: RunItem
    type: Literal["run_item_stream_event"] = "run_item_stream_event"

@dataclass
class AgentUpdatedStreamEvent:
    """Event that notifies that there is a new agent running."""
    new_agent: Agent[Any]
    type: Literal["agent_updated_stream_event"] = "agent_updated_stream_event"
```

### Runner.run_streamed()
1. 

```python
class Runner:
    @classmethod
    async def run_streamed(...) -> RunResultStreaming: # 函数签名同 .run, 实现不同
        if hooks is None:   # 下面四行同 .run
            hooks = RunHooks[Any]()
        if run_config is None:
            run_config = RunConfig()
        
        # If there's already a trace, we don't create a new one. In addition, we can't end the
        # trace here, because the actual work is done in `stream_events` and this method ends
        # before that.
        new_trace = (
            None
            if get_current_trace()
            else trace(
                workflow_name=run_config.workflow_name,
                trace_id=run_config.trace_id,
                group_id=run_config.group_id,
                metadata=run_config.trace_metadata,
                disabled=run_config.tracing_disabled,
            )
        )
        # Need to start the trace here, because the current trace contextvar is captured at
        # asyncio.create_task time
        if new_trace:
            new_trace.start(mark_as_current=True)

        output_schema = cls._get_output_schema(starting_agent)
        context_wrapper: RunContextWrapper[TContext] = RunContextWrapper(
            context=context  # type: ignore
        )

        streamed_result = RunResultStreaming(
            input=copy.deepcopy(input),
            new_items=[],
            current_agent=starting_agent,
            raw_responses=[],
            final_output=None,
            is_complete=False,
            current_turn=0,
            max_turns=max_turns,
            input_guardrail_results=[],
            output_guardrail_results=[],
            _current_agent_output_schema=output_schema,
            _trace=new_trace,
        )

        # Kick off the actual agent loop in the background and return the streamed result object.
        streamed_result._run_impl_task = asyncio.create_task(
            cls._run_streamed_impl(
                starting_input=input,
                streamed_result=streamed_result,
                starting_agent=starting_agent,
                max_turns=max_turns,
                hooks=hooks,
                context_wrapper=context_wrapper,
                run_config=run_config,
            )
        )
        return streamed_result
```




