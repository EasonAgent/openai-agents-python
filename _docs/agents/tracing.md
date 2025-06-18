
## Tracing
> [doc](https://openai.github.io/openai-agents-python/tracing/) 

1. Traces and Spans (记录的粒度)
    1. **Traces**: a single end-to-end operation of a "workflow", 包括 `workflow_name, trace_id, group_id, disabled, metadata` 字段
        1. ID 规范: 默认是自动生成的, 手动指定需要满足 `trace_<32_alphanumeric>` 格式. 
        2. 组织: 可以通过 group_id 来将多个 traces 关联起来, 例如一个 chat thread ID.
    2. **Spans**: operations that have a start and end time, 包括 `started_at, ended_at, trace_id, parent_id, span_data` 字段
        1. 其中, 核心的data可以是: `AgentSpanData` contains information about the Agent, `GenerationSpanData` contains information about the LLM generation, etc.
2. 默认行为
    - The entire `Runner.{run, run_sync, run_streamed}()` is wrapped in a `trace()`.
    - Each time an agent runs, it is wrapped in `agent_span()`
    - LLM generations are wrapped in `generation_span()`
    - Function tool calls are each wrapped in `function_span()`
    - Guardrails are wrapped in `guardrail_span()`
    - Handoffs are wrapped in `handoff_span()`
3. Higher level traces: 可以利用 `trace()` 方法来将多次的run封装到一个trace中 (e.g. 一次多轮对话)
4. 创建 traces:
    1. 可以通过 `trace(workflow_name, trace_id, group_id, metadata, disabled)` 来创建
    2. 参见 [contextvars](https://docs.python.org/3/library/contextvars.html), 提供两种使用方式:
        - **Recommended**: use the trace as a context manager, i.e. `with trace(...) as my_trace`. This will automatically start and end the trace at the right time.
        - You can also manually call `trace.start()` and `trace.finish()`.
5. 创建 spans: 
    1. 可以采用默认的一系列工具来创建, 包括: (下面的 ... 包括 `span_id, parent, disabled`; 而其他的输入则是SpanData所定义的数据结构)
        1. agent_span(name, handoffs, tools, output_type, ...)
        2. function_span(name, input, output, ...)
        3. generation_span(name, input, output, model, model_config, usage, ...)
        4. response_span(response, ...)
        5. handoff_span(from_agent, to_agent, ...)
        6. guardrail_span(name, triggered:bool, ...)
        7. custom_span(name, data:dict[str, Any], ...)
    2. SpanData 是对于span中所封装数据的抽象
        1. type: 包括 agent|generation|function|handoff|guardrail|response|custom
        2. export() 方法: 输出dict, 注意都应该是基础数据类别! 
6. 隐私: 在 RunConfig 中通过 `tracing_disabled, trace_include_sensitive_data` 配置
    1. 隐私数据包括: llm/tool 的输入输出 (同 logger)
7. 配置 processor
    1. 可以通过 `add_trace_processor(span_processor: TracingProcessor)` 来添加
    2. 通过 `set_trace_processors(processors: list[TracingProcessor])` 来设置所有的 processors
8. processors 实现机制
    1. 接口封装: 通过 `TraceProvider` 来提供服务抽象, 参见 `src/agents/tracing/setup.py` (在最开始的时候初始化)
    2. 并发处理: 通过 queue/threading 来实现并发, 参见 `src/agents/tracing/processor.py` 中的 BatchTraceProcessor 和 BackendSpanExporter
9. 外部 processors
    - [Arize-Phoenix](https://docs.arize.com/phoenix/tracing/integrations-tracing/openai-agents-sdk)
    - [MLflow](https://mlflow.org/docs/latest/tracing/integrations/openai-agent)
    - [Braintrust](https://braintrust.dev/docs/guides/traces/integrations#openai-agents-sdk)
    - [Pydantic Logfire](https://logfire.pydantic.dev/docs/integrations/llms/openai/#openai-agents)
    - [AgentOps](https://docs.agentops.ai/v1/integrations/agentssdk)
    - [Scorecard](https://docs.scorecard.io/docs/documentation/features/tracing#openai-agents-sdk-integration)
    - [Keywords AI](https://docs.keywordsai.co/integration/development-frameworks/openai-agent)
    - [LangSmith](https://docs.smith.langchain.com/observability/how_to_guides/trace_with_openai_agents_sdk)
    - [Maxim AI](https://www.getmaxim.ai/docs/observe/integrations/openai-agents-sdk)

### 数据结构: Traces and Spans

- **Traces** represent a single end-to-end operation of a "workflow". They're composed of Spans. Traces have the following properties:
    - `workflow_name`: This is the logical workflow or app. For example "Code generation" or "Customer service".
    - `trace_id`: A unique ID for the trace. Automatically generated if you don't pass one. Must have the format `trace_<32_alphanumeric>`.
    - `group_id`: Optional group ID, to link multiple traces from the same conversation. For example, you might use a chat thread ID.
    - `disabled`: If True, the trace will not be recorded.
    - `metadata`: Optional metadata for the trace.
- **Spans** represent operations that have a start and end time. Spans have:
    - `started_at` and `ended_at` timestamps.
    - `trace_id`, to represent the trace they belong to
    - `parent_id`, which points to the parent Span of this Span (if any)
    - `span_data`, which is information about the Span. For example, `AgentSpanData` contains information about the Agent, `GenerationSpanData` contains information about the LLM generation, etc.


### Trace
> 参见 [contextvars](https://docs.python.org/3/library/contextvars.html)


#### Trace 数据结构
```python
# src/agents/tracing/traces.py
class Trace:
    """
    A trace is the root level object that tracing creates. It represents a logical "workflow".
    """

    @abc.abstractmethod
    def __enter__(self) -> Trace:
        pass

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @abc.abstractmethod
    def start(self, mark_as_current: bool = False):
        """
        Start the trace.

        Args:
            mark_as_current: If true, the trace will be marked as the current trace.
        """
        pass

    @abc.abstractmethod
    def finish(self, reset_current: bool = False):
        """
        Finish the trace.

        Args:
            reset_current: If true, the trace will be reset as the current trace.
        """
        pass

    @property
    @abc.abstractmethod
    def trace_id(self) -> str:
        """
        The trace ID.
        """
        pass

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """
        The name of the workflow being traced.
        """
        pass

    @abc.abstractmethod
    def export(self) -> dict[str, Any] | None:
        """
        Export the trace as a dictionary.
        """
        pass
```

#### trace() 创建函数

```python
# src/agents/tracing/create.py
def trace(
    workflow_name: str,
    trace_id: str | None = None,
    group_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    disabled: bool = False,
) -> Trace:
    """
    Create a new trace. The trace will not be started automatically; you should either use
    it as a context manager (`with trace(...):`) or call `trace.start()` + `trace.finish()`
    manually.

    In addition to the workflow name and optional grouping identifier, you can provide
    an arbitrary metadata dictionary to attach additional user-defined information to
    the trace.

    Args:
        workflow_name: The name of the logical app or workflow. For example, you might provide
            "code_bot" for a coding agent, or "customer_support_agent" for a customer support agent.
        trace_id: The ID of the trace. Optional. If not provided, we will generate an ID. We
            recommend using `util.gen_trace_id()` to generate a trace ID, to guarantee that IDs are
            correctly formatted.
        group_id: Optional grouping identifier to link multiple traces from the same conversation
            or process. For instance, you might use a chat thread ID.
        metadata: Optional dictionary of additional metadata to attach to the trace.
        disabled: If True, we will return a Trace but the Trace will not be recorded. This will
            not be checked if there's an existing trace and `even_if_trace_running` is True.

    Returns:
        The newly created trace object.
    """
    current_trace = GLOBAL_TRACE_PROVIDER.get_current_trace()
    if current_trace:
        logger.warning(
            "Trace already exists. Creating a new trace, but this is probably a mistake."
        )

    return GLOBAL_TRACE_PROVIDER.create_trace(
        name=workflow_name,
        trace_id=trace_id,
        group_id=group_id,
        metadata=metadata,
        disabled=disabled,
    )


def get_current_trace() -> Trace | None:
    """Returns the currently active trace, if present."""
    return GLOBAL_TRACE_PROVIDER.get_current_trace()


def get_current_span() -> Span[Any] | None:
    """Returns the currently active span, if present."""
    return GLOBAL_TRACE_PROVIDER.get_current_span()
```


### Span

#### Span 定义

```python
# src/agents/tracing/spans.py
class Span(abc.ABC, Generic[TSpanData]):
    @property
    @abc.abstractmethod
    def trace_id(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def span_id(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def span_data(self) -> TSpanData:
        pass

    @abc.abstractmethod
    def start(self, mark_as_current: bool = False):
        """
        Start the span.

        Args:
            mark_as_current: If true, the span will be marked as the current span.
        """
        pass

    @abc.abstractmethod
    def finish(self, reset_current: bool = False) -> None:
        """
        Finish the span.

        Args:
            reset_current: If true, the span will be reset as the current span.
        """
        pass

    @abc.abstractmethod
    def __enter__(self) -> Span[TSpanData]:
        pass

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @property
    @abc.abstractmethod
    def parent_id(self) -> str | None:
        pass

    @abc.abstractmethod
    def set_error(self, error: SpanError) -> None:
        pass

    @property
    @abc.abstractmethod
    def error(self) -> SpanError | None:
        pass

    @abc.abstractmethod
    def export(self) -> dict[str, Any] | None:
        pass

    @property
    @abc.abstractmethod
    def started_at(self) -> str | None:
        pass

    @property
    @abc.abstractmethod
    def ended_at(self) -> str | None:
        pass
```

#### 创建 Spans

- 仅举一个例子

```python
# src/agents/tracing/create.py
def custom_span(
    name: str,
    data: dict[str, Any] | None = None,
    span_id: str | None = None,
    parent: Trace | Span[Any] | None = None,
    disabled: bool = False,
) -> Span[CustomSpanData]:
    """Create a new custom span, to which you can add your own metadata. The span will not be
    started automatically, you should either do `with custom_span() ...` or call
    `span.start()` + `span.finish()` manually.

    Args:
        name: The name of the custom span.
        data: Arbitrary structured data to associate with the span.
        span_id: The ID of the span. Optional. If not provided, we will generate an ID. We
            recommend using `util.gen_span_id()` to generate a span ID, to guarantee that IDs are
            correctly formatted.
        parent: The parent span or trace. If not provided, we will automatically use the current
            trace/span as the parent.
        disabled: If True, we will return a Span but the Span will not be recorded.

    Returns:
        The newly created custom span.
    """
    return GLOBAL_TRACE_PROVIDER.create_span(
        span_data=CustomSpanData(name=name, data=data or {}),
        span_id=span_id,
        parent=parent,
        disabled=disabled,
    )
```

#### SpanData

1. SpanData 是对于span中所封装数据的抽象
    1. type: 包括 agent|generation|function|handoff|guardrail|response|custom
    2. export() 方法: 输出dict, 注意都应该是基础数据类别! 
2. 对齐 create.py 中的 `*_span` 创建函数, 包括上述类别

```python
# src/agents/tracing/span_data.py
class SpanData(abc.ABC):
    @abc.abstractmethod
    def export(self) -> dict[str, Any]:
        pass

    @property
    @abc.abstractmethod
    def type(self) -> str:
        pass
```

实例1: AgentSpanData

```python
class AgentSpanData(SpanData):
    __slots__ = ("name", "handoffs", "tools", "output_type")

    def __init__(
        self,
        name: str,
        handoffs: list[str] | None = None,
        tools: list[str] | None = None,
        output_type: str | None = None,
    ):
        self.name = name
        self.handoffs: list[str] | None = handoffs
        self.tools: list[str] | None = tools
        self.output_type: str | None = output_type

    @property
    def type(self) -> str:
        return "agent"

    def export(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "name": self.name,
            "handoffs": self.handoffs,
            "tools": self.tools,
            "output_type": self.output_type,
        }
```



### processors

- 参见 `tests/test_trace_processor.py` TODO: 

```python
# src/agents/tracing/__init__.py
def add_trace_processor(span_processor: TracingProcessor) -> None:
    """
    Adds a new trace processor. This processor will receive all traces/spans.
    """
    GLOBAL_TRACE_PROVIDER.register_processor(span_processor)


def set_trace_processors(processors: list[TracingProcessor]) -> None:
    """
    Set the list of trace processors. This will replace the current list of processors.
    """
    GLOBAL_TRACE_PROVIDER.set_processors(processors)
```


