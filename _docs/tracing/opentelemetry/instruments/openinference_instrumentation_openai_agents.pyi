
from typing import Any, Collection, cast, Optional
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Mapping, Optional, Union
from datetime import datetime

""" --------------------------------------------------------------------------------------------------------------------
__init__.py
提供 OpenAIAgentsInstrumentor: 接入 OpenInference 体系!
    期中核心的是调用 openai_agents 里面的 set_trace_processors 来设置 Tracer 为这里实现好的 OpenInferenceTracingProcessor!
-------------------------------------------------------------------------------------------------------------------- """
# openinference/instrumentation/openai_agents/__init__.py
from agents import set_trace_processors
from . import _instruments
from ._instrumentor import OpenInferenceTracingProcessor
from opentelemetry import trace as trace_api
from openinference.instrumentation import OITracer, TraceConfig

class OpenAIAgentsInstrumentor(BaseInstrumentor):  # type: ignore
    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments
    def _instrument(self, **kwargs: Any) -> None:
        tracer_provider = trace_api.get_tracer_provider()
        config = TraceConfig()
        tracer = OITracer(
            trace_api.get_tracer(__name__, __version__, tracer_provider),
            config=config,
        )
        set_trace_processors([OpenInferenceTracingProcessor(cast(Tracer, tracer))])
    def _uninstrument(self, **kwargs: Any) -> None:
        pass


""" --------------------------------------------------------------------------------------------------------------------
OpenInferenceTracingProcessor(TracingProcessor): 核心实现
    自定义 TracingProcessor (from @agents)

> from openinference.instrumentation.openai_agents._processor import OpenInferenceTracingProcessor
-------------------------------------------------------------------------------------------------------------------- """
from agents.tracing import Span, Trace, TracingProcessor
from agents.tracing.span_data import ResponseSpanData, GenerationSpanData, FunctionSpanData, MCPListToolsSpanData
from openai.types.responses import Response, ResponseInputItemParam

from opentelemetry.context import attach, detach
from opentelemetry.trace import Status, StatusCode, Tracer, set_span_in_context
from opentelemetry.trace.span import Span as OtelSpan
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes, OpenInferenceLLMSystemValues, ToolAttributes, OpenInferenceMimeTypeValues
from openinference.instrumentation import safe_json_dumps
from opentelemetry.util.types import AttributeValue


class OpenInferenceTracingProcessor(TracingProcessor):
    def __init__(self, tracer: Tracer) -> None:         # 这里传入 otel 的 Tracer 类
        self._tracer = tracer
        self._root_spans: dict[str, OtelSpan] = {}
        self._otel_spans: dict[str, OtelSpan] = {}
        self._tokens: dict[str, object] = {}

    def on_trace_start(self, trace: Trace) -> None:
        # 设置为最外层的 span: agent
        otel_span = self._tracer.start_span(
            name=trace.name,
            attributes={OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.AGENT.value,}
        )
        self._root_spans[trace.trace_id] = otel_span
    def on_trace_end(self, trace: Trace) -> None:
        # 结束
        if root_span := self._root_spans.pop(trace.trace_id, None):
            root_span.set_status(Status(StatusCode.OK))
            root_span.end()
    
    def on_span_start(self, span: Span[Any]) -> None:
        """ 开始 span:
        - 搜集相关信息, 创建 otel 中的 Span
          - 设置 parent 关系
        - 根据 span.span_id 来设置 self._otel_spans 等字典
        """
        # ... get parent span
        start_time = datetime.fromisoformat(span.started_at)
        context = set_span_in_context(parent_span) if parent_span else None
        span_name = _get_span_name(span)
        otel_span = self._tracer.start_span(
            name=span_name,
            context=context,
            start_time=_as_utc_nano(start_time),
            attributes={
                OPENINFERENCE_SPAN_KIND: _get_span_kind(span.span_data),
                LLM_SYSTEM: OpenInferenceLLMSystemValues.OPENAI.value,
            },
        )
        self._otel_spans[span.span_id] = otel_span
        self._tokens[span.span_id] = attach(set_span_in_context(otel_span))
    def on_span_end(self, span: Span[Any]) -> None:
        """ 定义Span结束行为
        1. 根据 span.span_id 来从 self._otel_spans 等字典中获取对应的 otel_span
        2. 调用 otel_span.update_name()
        3. 调用 otel_span.set_attribute() 来保存对应部分的 @agents 传回的span数据
            ### 这里核心看 @agents 里面封装好的 SpanData 模型 ###
        4. 调用 otel_span.set_status()
        5. 调用 otel_span.end()
        """
        if not (otel_span := self._otel_spans.pop(span.span_id, None)): return
        otel_span.update_name(_get_span_name(span))
        data = span.span_data
        if isinstance(data, ResponseSpanData):
            if hasattr(data, "response") and isinstance(response := data.response, Response):
                otel_span.set_attribute(OUTPUT_MIME_TYPE, JSON)
                otel_span.set_attribute(OUTPUT_VALUE, response.model_dump_json())
                for k, v in _get_attributes_from_response(response):
                    otel_span.set_attribute(k, v)
            if hasattr(data, "input") and (input := data.input):
                if isinstance(input, str):
                    otel_span.set_attribute(INPUT_VALUE, input)
                elif isinstance(input, list):
                    otel_span.set_attribute(INPUT_MIME_TYPE, JSON)
                    otel_span.set_attribute(INPUT_VALUE, safe_json_dumps(input))
                    for k, v in _get_attributes_from_input(input):
                        otel_span.set_attribute(k, v)
                elif TYPE_CHECKING:
                    assert_never(input)
        elif isinstance(data, GenerationSpanData):
            for k, v in _get_attributes_from_generation_span_data(data):
                otel_span.set_attribute(k, v)
        elif isinstance(data, FunctionSpanData):
            for k, v in _get_attributes_from_function_span_data(data):
                otel_span.set_attribute(k, v)
        elif isinstance(data, MCPListToolsSpanData):
            for k, v in _get_attributes_from_mcp_list_tool_span_data(data):
                otel_span.set_attribute(k, v)
        otel_span.set_status(status=_get_span_status(span))
        otel_span.end(end_time)
    
    def force_flush(self) -> None:
        pass
    def shutdown(self) -> None:
        pass

def _get_attributes_from_generation_span_data(obj: GenerationSpanData) -> Iterator[tuple[str, AttributeValue]]:
    yield LLM_MODEL_NAME, obj.model
    yield LLM_INVOCATION_PARAMETERS, safe_json_dumps(obj.model_config)
    yield LLM_PROVIDER, OpenInferenceLLMProviderValues.OPENAI.value
    yield from _get_attributes_from_chat_completions_input(obj.input)
    yield from _get_attributes_from_chat_completions_output(obj.output)
    yield from _get_attributes_from_chat_completions_usage(obj.usage)

def _get_attributes_from_chat_completions_input(obj: Optional[Iterable[Mapping[str, Any]]]) -> Iterator[tuple[str, AttributeValue]]:
    yield INPUT_VALUE, safe_json_dumps(obj)
    yield INPUT_MIME_TYPE, JSON
    # 设置 prefix=="llm.input_messages"
    yield from _get_attributes_from_chat_completions_message_dicts(obj, f"{LLM_INPUT_MESSAGES}.",)

def _get_attributes_from_chat_completions_message_dicts(
    obj: Iterable[Mapping[str, Any]],
    prefix: str = "",
    msg_idx: int = 0,
    tool_call_idx: int = 0,
) -> Iterator[tuple[str, AttributeValue]]:
    for msg in obj:
        ...  # yield Messages 相关信息: role/content/tool_call_id/tool_calls


INPUT_MIME_TYPE = SpanAttributes.INPUT_MIME_TYPE
INPUT_VALUE = SpanAttributes.INPUT_VALUE
LLM_INPUT_MESSAGES = SpanAttributes.LLM_INPUT_MESSAGES
LLM_INVOCATION_PARAMETERS = SpanAttributes.LLM_INVOCATION_PARAMETERS
LLM_MODEL_NAME = SpanAttributes.LLM_MODEL_NAME
LLM_OUTPUT_MESSAGES = SpanAttributes.LLM_OUTPUT_MESSAGES
LLM_PROVIDER = SpanAttributes.LLM_PROVIDER
LLM_SYSTEM = SpanAttributes.LLM_SYSTEM
LLM_TOKEN_COUNT_COMPLETION = SpanAttributes.LLM_TOKEN_COUNT_COMPLETION
LLM_TOKEN_COUNT_PROMPT = SpanAttributes.LLM_TOKEN_COUNT_PROMPT
LLM_TOKEN_COUNT_TOTAL = SpanAttributes.LLM_TOKEN_COUNT_TOTAL
LLM_TOKEN_COUNT_PROMPT_DETAILS_CACHE_READ = SpanAttributes.LLM_TOKEN_COUNT_PROMPT_DETAILS_CACHE_READ
LLM_TOKEN_COUNT_COMPLETION_DETAILS_REASONING = SpanAttributes.LLM_TOKEN_COUNT_COMPLETION_DETAILS_REASONING
LLM_TOOLS = SpanAttributes.LLM_TOOLS
METADATA = SpanAttributes.METADATA
OPENINFERENCE_SPAN_KIND = SpanAttributes.OPENINFERENCE_SPAN_KIND
OUTPUT_MIME_TYPE = SpanAttributes.OUTPUT_MIME_TYPE
OUTPUT_VALUE = SpanAttributes.OUTPUT_VALUE
TOOL_DESCRIPTION = SpanAttributes.TOOL_DESCRIPTION
TOOL_NAME = SpanAttributes.TOOL_NAME
TOOL_PARAMETERS = SpanAttributes.TOOL_PARAMETERS

TOOL_JSON_SCHEMA = ToolAttributes.TOOL_JSON_SCHEMA

JSON = OpenInferenceMimeTypeValues.JSON.value
