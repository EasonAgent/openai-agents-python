from typing import Any, Callable, Generic
from dataclasses import dataclass

from .run import TContext, RunContextWrapper
from .agent import Agent
from .items import TResponseInputItem
from .utils import MaybeAwaitable

# --------------------------------------------------------------------------------
# Guardrail:
# --------------------------------------------------------------------------------
@dataclass
class InputGuardrail(Generic[TContext]):
    guardrail_function: Callable[[RunContextWrapper[TContext], Agent[Any], str | list[TResponseInputItem]], MaybeAwaitable[GuardrailFunctionOutput]]
    name: str | None = None
    def get_name(self) -> str: ...
    async def run(self, agent: Agent[Any], input: str | list[TResponseInputItem], context: RunContextWrapper[TContext]) -> InputGuardrailResult: ...

@dataclass
class OutputGuardrail(Generic[TContext]):
    guardrail_function: Callable[[RunContextWrapper[TContext], Agent[Any], Any], MaybeAwaitable[GuardrailFunctionOutput]]
    name: str | None = None
    def get_name(self) -> str: ...
    async def run(self, context: RunContextWrapper[TContext], agent: Agent[Any], agent_output: Any) -> OutputGuardrailResult: ...

@dataclass
class GuardrailFunctionOutput:
    output_info: Any
    tripwire_triggered: bool

@dataclass
class InputGuardrailResult:
    guardrail: InputGuardrail[Any]
    output: GuardrailFunctionOutput

@dataclass
class OutputGuardrailResult:
    guardrail: OutputGuardrail[Any]
    agent_output: Any
    agent: Agent[Any]
    output: GuardrailFunctionOutput
