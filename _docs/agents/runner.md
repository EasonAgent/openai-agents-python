## Runner

1. Runner: 封装 agent 的执行逻辑 (loop)
    1. Runner 所有都是类方法, 不存储信息! (信息放到 Context 等其他组件中)
2. 执行逻辑
    - 开始: 从传入的agent (current_agent) 开始
    - 循环: 在有 `final_output` 时结束 (或者到达 `max_turns`)
    - 终止: (final_output 逻辑) 有文本的回复, 同时没有工具调用
3. 返回: 标准化的 `RunResult` 或 `RunResultStreaming`
4. 封装方案:
    1. `Runner.run()`: 异步执行
    2. `Runner.run_sync()`: 同步执行
    3. `Runner.run_streamed()`: 流式执行
5. 提供三种接口: run, run_sync, run_streamed
    1. `run(cls, starting_agent, input, *, context, max_turns, hooks, run_config) -> RunResult`
    2. `run_sync`: 非异步执行
    3. `run_streamed(...) -> RunResultStreaming`: 流式执行, 参数同 run, 返回 `RunResultStreaming`
6. `RunResult` 和 `RunResultStreaming` 
    1. 相同字段: input, new_items, raw_responses, final_output, input_guardrail_results, output_guardrail_results, last_agent, to_input_list()
7. RunItem 和 ModelResponse

### 执行逻辑 (loop)

1. We call the LLM for the current agent, with the current input.
2. The LLM produces its output.
    1. If the LLM returns a `final_output`, the loop ends and we return the result.
    2. If the LLM does a handoff, we update the current agent and input, and re-run the loop.
    3. If the LLM produces tool calls, we run those tool calls, append the results, and re-run the loop.
3. If we exceed the `max_turns` passed, we raise a [`MaxTurnsExceeded`](https://openai.github.io/openai-agents-python/ref/exceptions/#agents.exceptions.MaxTurnsExceeded "MaxTurnsExceeded") exception.

> The rule for whether the LLM output is considered as a "final output" is that it produces text output with the desired type, and there are no tool calls.

### RunConfig

- `model`: Allows setting a global LLM model to use, irrespective of what model each Agent has.
- `model_provider`: A model provider for looking up model names, which defaults to OpenAI.
- `model_settings`: Overrides agent-specific settings. For example, you can set a global temperature or top_p.
- `input_guardrails`, `output_guardrails`: A list of input or output guardrails to include on all runs.
- `handoff_input_filter`: A global input filter to apply to all handoffs, if the handoff doesn't already have one. The input filter allows you to edit the inputs that are sent to the new agent. See the documentation in Handoff.input_filter for more details.
- `tracing_disabled`: Allows you to disable tracing for the entire run.
- `trace_include_sensitive_data`: Configures whether traces will include potentially sensitive data, such as LLM and tool call inputs/outputs.
- `workflow_name`, `trace_id`, `group_id`: Sets the tracing workflow name, trace ID and trace group ID for the run. We recommend at least setting workflow_name. The session ID is an optional field that lets you link traces across multiple runs.
- `trace_metadata`: Metadata to include on all traces.

### Exceptions
- `AgentsException` is the base class for all exceptions raised in the SDK.
    - 除了 guardrail, 基类下面的其他异常包括一个 `message: str` 字段
- `MaxTurnsExceeded` is raised when the run exceeds the max_turns passed to the run methods.
- `ModelBehaviorError` is raised when the model produces invalid outputs, e.g. malformed JSON or using non-existent tools.
- `UserError` is raised when you (the person writing code using the SDK) make an error using the SDK.
- `InputGuardrailTripwireTriggered`, `OutputGuardrailTripwireTriggered` is raised when a guardrail is tripped.
    - 包括一个 guardrail_result 字段

### lifecycle | hooks

- 参见 lifecycle 中的 `RunHooks` 和 `AgentHooks`
- RunHooks: 包括以下关键节点
    - 开始结束: agent_start(context, agent), agent_end(context, agent, output)
    - 交接: handoff(context, from_agent, to_agent)
    - 工具: tool_start(context, agent, tool), tool_end(context, agent, tool, result)
- AgentHooks: 包括以下关键节点
    - 开始结束: start(context, agent), end(context, agent, output)
    - 交接: handoff(context, agent, source)
    - 工具: tool_start(context, agent, tool), tool_end(context, agent, tool, result)

### Runner.run()

1. 概念: turn 是整个run级别的迭代次数 (设置 `max_turns`), 而 span 则是这一轮次中单个agent的决策序列. 
2. 代码组件
    1. `current_turn`: 当前turns
    2. `generated_items: list[RunItem]`: 生成的 items
    3. `current_span: Span[AgentSpanData]`: 通过span来组织不同agents的链路
3. 其他组件
    1. `TraceCtxManager`: 用于管理trace
    2. `RunConfig`
    3. `RunHooks`
4. 参考: Runner 所有都是类方法, 不存储信息! (信息放到 Context 等其他组件中)
5. 返回: `RunResult`, 见下
6. 对于流式方案, 见下


```python

```

### RunResult

1. `RunResultBase` 定义了两种模式共用的字段
    1. `input: str | list[TResponseInputItem]`: 原本的输入 (可能会有 filter 等变换) -- 对齐 `openai.types.responses.ResponseInputItemParam`
    2. `new_items: list[RunItem]`: 新生成的 items, 包括 new messages, tool calls, etc.
    3. `raw_responses: list[ModelResponse]`: LLM 的原始响应
    4. `final_output: Any`: 最终的输出. 默认为 str, 若执行了输出格式, 则类型为 `last_agent.output_type`
    5. `input_guardrail_results: list[InputGuardrailResult]`
    6. `output_guardrail_results: list[OutputGuardrailResult]`
    7. `last_agent: Agent[Any]`: 最后所执行的 agent 指针! 可以用于下一轮的交互
    8. `to_input_list() -> list[TResponseInputItem]`: 转换为 input list, 用于下一次 run
2. `RunItem`: agent 的输出
    1. 类型: `RunItem: TypeAlias = Union[MessageOutputItem, HandoffCallItem, HandoffOutputItem, ToolCallItem, ToolCallOutputItem, ReasoningItem]`
    2. 对应的 type: message_output_item|handoff_call_item|handoff_output_item|tool_call_item|tool_call_output_item|reasoning_item
    3. 比较 responses API? 
        1. 通过 `raw_item` 存储原始的输出. 可以是responses 中的 `ResponseInputItemParam` 或 `ResponseOutputItem`;
        2. 增加 agent 指针;
        3. 增加 `to_input_item() -> TResponseInputItem` 方法转为输入 (dict)
3. `ModelResponse`: LLM 的输出
    1. 比较 responses API? 简单封装 ResponseOutputItem
        1. 通过 `output` 存储原始的输出
        2. 新增 `usage`, `referenceable_id` 字段
        3. 新增 `to_input_items() -> list[TResponseInputItem]` 方法
4. 对于流式形式, 参见 streaming 部分

```python
# src/agents/result.py
@dataclass
class RunResultBase(abc.ABC):
    input: str | list[TResponseInputItem]
    """The original input items i.e. the items before run() was called. This may be a mutated
    version of the input, if there are handoff input filters that mutate the input.
    """

    new_items: list[RunItem]
    """The new items generated during the agent run. These include things like new messages, tool
    calls and their outputs, etc.
    """

    raw_responses: list[ModelResponse]
    """The raw LLM responses generated by the model during the agent run."""

    final_output: Any
    """The output of the last agent."""

    input_guardrail_results: list[InputGuardrailResult]
    """Guardrail results for the input messages."""

    output_guardrail_results: list[OutputGuardrailResult]
    """Guardrail results for the final output of the agent."""

    def final_output_as(self, cls: type[T], raise_if_incorrect_type: bool = False) -> T:
        """A convenience method to cast the final output to a specific type. By default, the cast
        is only for the typechecker. If you set `raise_if_incorrect_type` to True, we'll raise a
        TypeError if the final output is not of the given type.

        Args:
            cls: The type to cast the final output to.
            raise_if_incorrect_type: If True, we'll raise a TypeError if the final output is not of
                the given type.

        Returns:
            The final output casted to the given type.
        """
        return cast(T, self.final_output)

    def to_input_list(self) -> list[TResponseInputItem]:
        """Creates a new input list, merging the original input with all the new items generated."""
        original_items: list[TResponseInputItem] = ItemHelpers.input_to_new_input_list(self.input)
        new_items = [item.to_input_item() for item in self.new_items]
        return original_items + new_items
```

```python
@dataclass
class RunResult(RunResultBase):
    _last_agent: Agent[Any]

    @property
    def last_agent(self) -> Agent[Any]:
        """The last agent that was run."""
        return self._last_agent

    def __str__(self) -> str:
        return pretty_print_result(self)
```


### agent 输出: RunItem
- RunItem: TypeAlias = Union[MessageOutputItem, HandoffCallItem, HandoffOutputItem, ToolCallItem, ToolCallOutputItem, ReasoningItem]
```python
# src/agents/items.py
TResponseInputItem = ResponseInputItemParam
"""A type alias for the ResponseInputItemParam type from the OpenAI SDK."""
TResponseOutputItem = ResponseOutputItem
"""A type alias for the ResponseOutputItem type from the OpenAI SDK."""
T = TypeVar("T", bound=Union[TResponseOutputItem, TResponseInputItem])

@dataclass
class RunItemBase(Generic[T], abc.ABC):
    agent: Agent[Any]
    """The agent whose run caused this item to be generated."""

    raw_item: T
    """The raw Responses item from the run. This will always be a either an output item (i.e.
    `openai.types.responses.ResponseOutputItem` or an input item
    (i.e. `openai.types.responses.ResponseInputItemParam`).
    """

    def to_input_item(self) -> TResponseInputItem:
        """Converts this item into an input item suitable for passing to the model."""
        if isinstance(self.raw_item, dict):
            # We know that input items are dicts, so we can ignore the type error
            return self.raw_item  # type: ignore
        elif isinstance(self.raw_item, BaseModel):
            # All output items are Pydantic models that can be converted to input items.
            return self.raw_item.model_dump(exclude_unset=True)  # type: ignore
        else:
            raise AgentsException(f"Unexpected raw item type: {type(self.raw_item)}")
```


### LLM 输出: ModelResponse

```python
# src/agents/items.py
@dataclass
class ModelResponse:
    output: list[TResponseOutputItem]
    """A list of outputs (messages, tool calls, etc) generated by the model"""

    usage: Usage
    """The usage information for the response."""

    referenceable_id: str | None
    """An ID for the response which can be used to refer to the response in subsequent calls to the
    model. Not supported by all model providers.
    """

    def to_input_items(self) -> list[TResponseInputItem]:
        """Convert the output into a list of input items suitable for passing to the model."""
        # We happen to know that the shape of the Pydantic output items are the same as the
        # equivalent TypedDict input items, so we can just convert each one.
        # This is also tested via unit tests.
        return [it.model_dump(exclude_unset=True) for it in self.output]  # type: ignore

```


### 单步运行逻辑 _run_single_turn

1. 输入输出: 返回标准化的 `SingleStepResult`

```python
    @classmethod
    async def _run_single_turn(
        cls,
        *,
        agent: Agent[TContext],
        original_input: str | list[TResponseInputItem],
        generated_items: list[RunItem],
        hooks: RunHooks[TContext],
        context_wrapper: RunContextWrapper[TContext],
        run_config: RunConfig,
        should_run_agent_start_hooks: bool,
    ) -> SingleStepResult:
        # agent 开始的时候运行 hooks
        if should_run_agent_start_hooks:
            ...
        
        # 组织 prompt 给agent
        system_prompt = await agent.get_system_prompt(context_wrapper)
        output_schema = cls._get_output_schema(agent)
        handoffs = cls._get_handoffs(agent)
        input = ItemHelpers.input_to_new_input_list(original_input)
        input.extend([generated_item.to_input_item() for generated_item in generated_items])

        new_response = await cls._get_new_response(...) # see 模型调用
        return await cls._get_single_step_result_from_response(...)
```

### 模型调用
```python
    @classmethod
    async def _get_new_response(
        cls,
        agent: Agent[TContext],
        system_prompt: str | None,
        input: list[TResponseInputItem],
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
        context_wrapper: RunContextWrapper[TContext],
        run_config: RunConfig,
    ) -> ModelResponse:
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
```

### RunImpl TODO:

```python
    @classmethod
    async def _get_single_step_result_from_response(
        cls,
        *,
        agent: Agent[TContext],
        original_input: str | list[TResponseInputItem],
        pre_step_items: list[RunItem],
        new_response: ModelResponse,
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
        hooks: RunHooks[TContext],
        context_wrapper: RunContextWrapper[TContext],
        run_config: RunConfig,
    ) -> SingleStepResult:
        processed_response = RunImpl.process_model_response(...)
        return await RunImpl.execute_tools_and_side_effects(...)
```

```python
# src/agents/_run_impl.py
@dataclass
class ProcessedResponse:
    new_items: list[RunItem]
    handoffs: list[ToolRunHandoff]
    functions: list[ToolRunFunction]
    computer_actions: list[ToolRunComputerAction]

    def has_tools_to_run(self) -> bool:
        # Handoffs, functions and computer actions need local processing
        # Hosted tools have already run, so there's nothing to do.
        return any(
            [
                self.handoffs,
                self.functions,
                self.computer_actions,
            ]
        )


class RunImpl:
    @classmethod
    def process_model_response(
        cls,
        *,
        agent: Agent[Any],
        response: ModelResponse,
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
    ) -> ProcessedResponse:
```


```python
class RunImpl:
    @classmethod
    async def execute_tools_and_side_effects(
        cls,
        *,
        agent: Agent[TContext],
        # The original input to the Runner
        original_input: str | list[TResponseInputItem],
        # Everything generated by Runner since the original input, but before the current step
        pre_step_items: list[RunItem],
        new_response: ModelResponse,
        processed_response: ProcessedResponse,
        output_schema: AgentOutputSchema | None,
        hooks: RunHooks[TContext],
        context_wrapper: RunContextWrapper[TContext],
        run_config: RunConfig,
    ) -> SingleStepResult:
```



