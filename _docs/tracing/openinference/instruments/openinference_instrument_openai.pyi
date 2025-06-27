from typing import Any, Collection, cast, Optional
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Mapping, Optional, Union
from abc import ABC

""" --------------------------------------------------------------------------------------------------------------------
__init__.py
提供 OpenAIAgentsInstrumentor: 接入 OpenInference 体系!
    期中核心的是调用 openai_agents 里面的 set_trace_processors 来设置 Tracer 为这里实现好的 OpenInferenceTracingProcessor!

> from openinference.instrumentation.openai import OpenAIInstrumentor
-------------------------------------------------------------------------------------------------------------------- """

from importlib import import_module
from wrapt import wrap_function_wrapper
# from .package import OpenInferenceTracingProcessor
from opentelemetry import trace as trace_api
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor  # type: ignore
from openinference.instrumentation import OITracer, TraceConfig

_MODULE = "openai"
_instruments = ("openai >= 1.69.0",)

class OpenAIInstrumentor(BaseInstrumentor):  # type: ignore
    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs: Any) -> None:
        tracer_provider = trace_api.get_tracer_provider()
        config = TraceConfig()
        tracer = OITracer(
            trace_api.get_tracer(__name__, __version__, tracer_provider),
            config=config,
        )
        openai = import_module(_MODULE)
        self._original_request = openai.OpenAI.request
        self._original_async_request = openai.AsyncOpenAI.request
        wrap_function_wrapper(
            module=_MODULE,
            name="OpenAI.request",
            wrapper=_Request(tracer=tracer, openai=openai),
        )
        wrap_function_wrapper(
            module=_MODULE,
            name="AsyncOpenAI.request",
            wrapper=_AsyncRequest(tracer=tracer, openai=openai),
        )

    def _uninstrument(self, **kwargs: Any) -> None:
        openai = import_module(_MODULE)
        openai.OpenAI.request = self._original_request
        openai.AsyncOpenAI.request = self._original_async_request


""" --------------------------------------------------------------------------------------------------------------------
_Request: 拦截 OpenAI.request 请求

> from openinference.instrumentation.openai._request import _Request, _AsyncRequest
-------------------------------------------------------------------------------------------------------------------- """
# from openai

class _WithTracer(ABC):
    def __init__(self, tracer: trace_api.Tracer, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tracer = tracer

class _WithOpenAI(ABC):
    def __init__(self, openai: ModuleType, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._openai = openai
        self._stream_types = (openai.Stream, openai.AsyncStream)
        self._request_attributes_extractor = _RequestAttributesExtractor(openai=openai)
        self._response_attributes_extractor = _ResponseAttributesExtractor(openai=openai)

class _Request(_WithTracer, _WithOpenAI):
    def __call__(
        self,
        wrapped: Callable[..., Any],
        instance: Any,
        args: Tuple[type, Any],
        kwargs: Mapping[str, Any],
    ) -> Any:
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return wrapped(*args, **kwargs)
        # TODO: