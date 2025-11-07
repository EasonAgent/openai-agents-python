
## Tracing
> [doc](https://openai.github.io/openai-agents-python/tracing/) 
> 参见 [contextvars](https://docs.python.org/3/library/contextvars.html)

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
