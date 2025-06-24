import abc
from abc import ABC
from typing import Any, Generic
from typing_extensions import TypeVar, TypedDict


TSpanData = TypeVar("TSpanData", bound=SpanData)

""" --------------------------------------------------------------------------------------------------------------------
Span
-------------------------------------------------------------------------------------------------------------------- """
# src/agents/tracing/spans.py
class Span(abc.ABC, Generic[TSpanData]):
    def trace_id(self) -> str: ...
    def span_id(self) -> str: ...
    def span_data(self) -> TSpanData: ...

    def start(self, mark_as_current: bool = False): ...
    def finish(self, reset_current: bool = False) -> None: ...
    def __enter__(self) -> Span[TSpanData]: ...
    def __exit__(self, exc_type, exc_val, exc_tb): ...

    def parent_id(self) -> str | None: ...
    def set_error(self, error: SpanError) -> None: ...
    def error(self) -> SpanError | None: ...
    def export(self) -> dict[str, Any] | None: ...
    def started_at(self) -> str | None: ...
    def ended_at(self) -> str | None: ...

class SpanError(TypedDict):
    message: str
    data: dict[str, Any] | None


""" --------------------------------------------------------------------------------------------------------------------
SpanData

1. SpanData 是对于span中所封装数据的抽象
    1. type: 包括 agent|generation|function|handoff|guardrail|response|custom
    2. export() 方法: 输出dict, 注意都应该是基础数据类别! 
2. 对齐 create.py 中的 `*_span` 创建函数, 包括上述类别
-------------------------------------------------------------------------------------------------------------------- """
class SpanData(abc.ABC):
    def export(self) -> dict[str, Any]:
        """Export the span data as a dictionary."""
    def type(self) -> str:
        """Return the type of the span."""

class AgentSpanData(SpanData):
    """Represents an Agent Span in the trace."""
    __slots__ = ("name", "handoffs", "tools", "output_type")
    def __init__(self, name: str, handoffs: list[str] | None = None, tools: list[str] | None = None, output_type: str | None = None):
        ...
    @property
    def type(self) -> str:
        return "agent"
    def export(self) -> dict[str, Any]:
        return {...}


""" --------------------------------------------------------------------------------------------------------------------
Trace
-------------------------------------------------------------------------------------------------------------------- """
# src/agents/tracing/traces.py
class Trace:
    """ A trace is the root level object that tracing creates. It represents a logical "workflow". """
    @abc.abstractmethod
    def __enter__(self) -> Trace: ...
    @abc.abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb): ...
    @abc.abstractmethod
    def start(self, mark_as_current: bool = False): ...
    @abc.abstractmethod
    def finish(self, reset_current: bool = False): ...

    @property
    @abc.abstractmethod
    def trace_id(self) -> str: ...
    @property
    @abc.abstractmethod
    def name(self) -> str: ...
    @abc.abstractmethod
    def export(self) -> dict[str, Any] | None: ...

class TraceProvider:
    def register_processor(self, processor: TracingProcessor): ...
    def set_processors(self, processors: list[TracingProcessor]): ...
    def get_current_trace(self) -> Trace | None:
        return Scope.get_current_trace()
    def get_current_span(self) -> Span[Any] | None:
        return Scope.get_current_span()
    def set_disabled(self, disabled: bool) -> None:
        self._disabled = disabled

    def create_trace(self, name: str, trace_id: str | None = None, group_id: str | None = None, metadata: dict[str, Any] | None = None, disabled: bool = False) -> Trace: ...
    def create_span(self, span_data: TSpanData, span_id: str | None = None, parent: Trace | Span[Any] | None = None, disabled: bool = False) -> Span[TSpanData]: ...
    def shutdown(self) -> None: ...


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
    return get_trace_provider().create_trace(...)

def get_current_trace() -> Trace | None:
    """Returns the currently active trace, if present."""
    return get_trace_provider().get_current_trace()
def get_current_span() -> Span[Any] | None:
    """Returns the currently active span, if present."""
    return get_trace_provider().get_current_span()


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
    return get_trace_provider().create_span(...)


""" --------------------------------------------------------------------------------------------------------------------
Tracing
-------------------------------------------------------------------------------------------------------------------- """
# src/agents/tracing/provider.py
class TraceProvider(ABC):
    """Interface for creating traces and spans."""
    def register_processor(self, processor: TracingProcessor) -> None:
        """Add a processor that will receive all traces and spans."""
    def set_processors(self, processors: list[TracingProcessor]) -> None:
        """Replace the list of processors with ``processors``."""
    def get_current_trace(self) -> Trace | None:
        """Return the currently active trace, if any."""
    def get_current_span(self) -> Span[Any] | None:
        """Return the currently active span, if any."""
    def set_disabled(self, disabled: bool) -> None:
        """Enable or disable tracing globally."""
    def time_iso(self) -> str:
        """Return the current time in ISO 8601 format."""
    def gen_trace_id(self) -> str:
        """Generate a new trace identifier."""
    def gen_span_id(self) -> str:
        """Generate a new span identifier."""
    def gen_group_id(self) -> str:
        """Generate a new group identifier."""
    def create_trace(self, name: str, trace_id: str | None = None, group_id: str | None = None, metadata: dict[str, Any] | None = None, disabled: bool = False) -> Trace:
        """Create a new trace."""
    def create_span(self, span_data: TSpanData, span_id: str | None = None, parent: Trace | Span[Any] | None = None, disabled: bool = False) -> Span[TSpanData]:
        """Create a new span."""
    def shutdown(self) -> None:
        """Clean up any resources used by the provider."""

""" --------------------------------------------------------------------------------------------------------------------
Holds the current active span

# src/agents/tracing/scope.py
-------------------------------------------------------------------------------------------------------------------- """
import contextvars
from typing import TYPE_CHECKING, Any

_current_span: contextvars.ContextVar["Span[Any] | None"] = contextvars.ContextVar("current_span", default=None)
_current_trace: contextvars.ContextVar["Trace | None"] = contextvars.ContextVar("current_trace", default=None)

class Scope:
    """ Manages the current span and trace in the context. """
    @classmethod
    def get_current_span(cls) -> "Span[Any] | None":
        return _current_span.get()
    @classmethod
    def set_current_span(cls, span: "Span[Any] | None") -> "contextvars.Token[Span[Any] | None]":
        return _current_span.set(span)
    @classmethod
    def reset_current_span(cls, token: "contextvars.Token[Span[Any] | None]") -> None:
        _current_span.reset(token)
    @classmethod
    def get_current_trace(cls) -> "Trace | None":
        return _current_trace.get()
    @classmethod
    def set_current_trace(cls, trace: "Trace | None") -> "contextvars.Token[Trace | None]":
        return _current_trace.set(trace)
    @classmethod
    def reset_current_trace(cls, token: "contextvars.Token[Trace | None]") -> None:
        _current_trace.reset(token)