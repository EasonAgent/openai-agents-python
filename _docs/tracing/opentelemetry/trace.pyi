import abc, typing
from abc import ABC
from typing import Iterator, Optional


""" --------------------------------------------------------------------------------------------------------------------
Tracer: 处理相关输出, 产生 Span

> from opentelemetry.trace import Tracer
-------------------------------------------------------------------------------------------------------------------- """
class Tracer(ABC):
    """Handles span creation and in-process context propagation.
    This class provides methods for manipulating the context, creating spans,
    and controlling spans' lifecycles.
    """
    def start_span(
        self,
        name: str,
        context: Optional[Context] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: types.Attributes = None,
        links: _Links = None,
        start_time: Optional[int] = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
    ) -> "Span":
        ...

    def start_as_current_span(
        self,
        name: str,
        context: Optional[Context] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: types.Attributes = None,
        links: _Links = None,
        start_time: Optional[int] = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
        end_on_exit: bool = True,
    ) -> Iterator["Span"]:
        ...


""" --------------------------------------------------------------------------------------------------------------------
Span
> from opentelemetry.trace.span import Span
-------------------------------------------------------------------------------------------------------------------- """
import types as python_types
from opentelemetry.util import types
from opentelemetry.trace.status import Status, StatusCode

class Span(abc.ABC):
    def end(self, end_time: typing.Optional[int] = None) -> None:
        """Sets the current time as the span's end time."""

    def get_span_context(self) -> "SpanContext":
        """Gets the span's SpanContext.
        Get an immutable, serializable identifier for this span that can be
        used to create new child spans."""

    def set_attributes(self, attributes: typing.Mapping[str, types.AttributeValue]) -> None:
        """Sets Attributes.
        Sets Attributes with the key and value passed as arguments dict."""
    def set_attribute(self, key: str, value: types.AttributeValue) -> None:
        """Sets an Attribute.
        Sets a single Attribute with the key and value passed as arguments."""

    def add_event(self, name: str, attributes: types.Attributes = None, timestamp: typing.Optional[int] = None) -> None:
        """Adds an `Event`."""
    # def add_link(  # pylint: disable=no-self-use
    def update_name(self, name: str) -> None:
        """Updates the `Span` name.
        This will override the name provided via :func:`opentelemetry.trace.Tracer.start_span`."""
    def is_recording(self) -> bool:
        """Returns whether this span will be recorded."""
    def set_status(self, status: typing.Union[Status, StatusCode], description: typing.Optional[str] = None) -> None:
        """Sets the Status of the Span. If used, this will override the default Span status."""
    def record_exception(self, exception: BaseException, attributions: types.Attributes = None, timestamp: typing.Optional[int] = None, escaped: bool = False) -> None:
        """Records an exception as a span event."""
    
    def __enter__(self) -> "Span": ...
    def __exit__(self, exc_type: typing.Optional[type], exc_val: typing.Optional[BaseException], exc_tb: typing.Optional[python_types.TracebackType]) -> None: ...



""" --------------------------------------------------------------------------------------------------------------------
Span
> from opentelemetry.trace.propagation import set_span_in_context, get_current_span
-------------------------------------------------------------------------------------------------------------------- """
from .context import create_key, Context, set_value, get_value

SPAN_KEY = "current-span"
_SPAN_KEY = create_key("current-span")

def set_span_in_context(span: Span, context: Optional[Context] = None) -> Context:
    """Set the span in the given context.
    Args:
        span: The Span to set.
        context: a Context object. if one is not passed, the default current context is used instead.
    """
    ctx = set_value(_SPAN_KEY, span, context=context)
    return ctx

def get_current_span(context: Optional[Context] = None) -> Span:
    """Retrieve the current span."""
    span = get_value(_SPAN_KEY, context=context)
    if span is None or not isinstance(span, Span):
        return INVALID_SPAN
    return span
