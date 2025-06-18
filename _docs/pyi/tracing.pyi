import abc
from typing import Any, Generic
from typing_extensions import TypeVar, TypedDict


""" --------------------------------------------------------------------------------------------------------------------
Tracing
-------------------------------------------------------------------------------------------------------------------- """
TSpanData = TypeVar("TSpanData", bound=SpanData)

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

class SpanData(abc.ABC):
    def export(self) -> dict[str, Any]: ...
    def type(self) -> str: ...

class AgentSpanData(SpanData):
    """Represents an Agent Span in the trace."""
    __slots__ = ("name", "handoffs", "tools", "output_type")
    @property
    def type(self) -> str:
        return "agent"
    def export(self) -> dict[str, Any]: ...


def get_current_trace() -> Trace | None:
    """Returns the currently active trace, if present."""
    return GLOBAL_TRACE_PROVIDER.get_current_trace()


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