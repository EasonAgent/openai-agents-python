from openai.types.responses import ResponseCompletedEvent
from openai.types.responses.response_prompt_param import ResponsePromptParam
from openai.types.responses import ResponseFunctionToolCall

from .tool import Tool, Handoff, FunctionTool
from .tracing import AgentSpanData, get_current_trace, Span


""" --------------------------------------------------------------------------------------------------------------------
RunImpl: 运行实现
    顶层接口:
        execute_tools_and_side_effects(...) -> SingleStepResult 执行工具
            execute_function_tool_calls | execute_computer_actions | execute_handoffs
        run_single_input_guardrail(...) -> InputGuardrailResult
        run_single_output_guardrail(...) -> OutputGuardrailResult
    辅助函数:
        process_model_response(agent, response, output_schema, handoffs) -> ProcessedResponse. 转为 RunImpl 执行过程的中间数据 (用于 execute_tools_and_side_effects)

    @classmethod # 会调用 cls.execute_function_tool_calls | cls.execute_computer_actions | cls.execute_handoffs
    async def execute_tools_and_side_effects(cls, *, agent: Agent[TContext], original_input: str | list[TResponseInputItem], pre_step_items: list[RunItem], new_response: ModelResponse, processed_response: ProcessedResponse, output_schema: AgentOutputSchemaBase | None, hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> SingleStepResult: ...
    @classmethod
    def process_model_response(cls, *, agent: Agent[Any], response: ModelResponse, output_schema: AgentOutputSchemaBase | None, handoffs: list[Handoff]) -> ProcessedResponse: ...
    
    @classmethod
    async def execute_function_tool_calls(cls, *, agent: Agent[TContext], tool_runs: list[ToolRunFunction], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], config: RunConfig) -> list[FunctionToolResult]: ...
    @classmethod
    async def execute_computer_actions(cls, *, agent: Agent[TContext], actions: list[ToolRunComputerAction], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], config: RunConfig) -> list[RunItem]: ...
    @classmethod
    async def execute_handoffs(cls, *, agent: Agent[TContext], original_input: str | list[TResponseInputItem], pre_step_items: list[RunItem], new_step_items: list[RunItem], new_response: ModelResponse, run_handoffs: list[ToolRunHandoff], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> SingleStepResult: ...
    @classmethod # -> cls.run_final_output_hooks
    async def execute_final_output(cls, *, agent: Agent[TContext], original_input: str | list[TResponseInputItem], new_response: ModelResponse, pre_step_items: list[RunItem], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], run_config: RunConfig) -> SingleStepResult: ...
    @classmethod
    async def run_final_output_hooks(cls, agent: Agent[TContext], hooks: RunHooks[TContext], context_wrapper: RunContextWrapper[TContext], final_output: Any): ...
    
    @classmethod
    async def run_single_input_guardrail(cls, agent: Agent[Any], guardrail: InputGuardrail[TContext], input: str | list[TResponseInputItem], context: RunContextWrapper[TContext]) -> InputGuardrailResult: ...
    @classmethod
    async def run_single_output_guardrail(cls, guardrail: OutputGuardrail[TContext], agent: Agent[Any], agent_output: Any, context: RunContextWrapper[TContext]) -> OutputGuardrailResult: ...

    @classmethod # 将流式的一个 step result 中的信息放到 queue 中
    def stream_step_result_to_queue(cls, step_result: SingleStepResult, queue: asyncio.Queue[StreamEvent | QueueCompleteSentinel]): ...
    @classmethod
    async def _check_for_final_output_from_tools(cls, *, agent: Agent[TContext], tool_results: list[FunctionToolResult], context_wrapper: RunContextWrapper[TContext], config: RunConfig) -> ToolsToFinalOutputResult: ...
-------------------------------------------------------------------------------------------------------------------- """

class RunImpl:
    @classmethod
    async def execute_tools_and_side_effects() -> SingleStepResult:
        """  """
    def maybe_reset_tool_choice() -> ModelSettings:
        """  """
    def process_model_response() -> ProcessedResponse:
        """  """
    async def execute_function_tool_calls() -> list[FunctionToolResult]:
        """  """
    async def execute_local_shell_calls():
        """  """
    async def execute_computer_actions() -> list[RunItem]:
        """  """
    async def execute_handoffs() -> SingleStepResult:
        """  """
    async def execute_mcp_approval_requests() -> list[RunItem]:
        """  """
    async def execute_final_output() -> SingleStepResult:
        """  """
    async def run_final_output_hooks():
        """  """
    async def run_single_input_guardrail() -> InputGuardrailResult:
        """  """
    async def run_single_output_guardrail() -> OutputGuardrailResult:
        """  """
    def stream_step_result_to_queue():
        """  """
    async def _check_for_final_output_from_tools() -> ToolsToFinalOutputResult:
        """  """

@dataclass
class ProcessedResponse:
    new_items: list[RunItem]
    handoffs: list[ToolRunHandoff]
    functions: list[ToolRunFunction]
    computer_actions: list[ToolRunComputerAction]
@dataclass
class ToolRunHandoff:
    handoff: Handoff
    tool_call: ResponseFunctionToolCall
@dataclass
class ToolRunFunction:
    tool_call: ResponseFunctionToolCall
    function_tool: FunctionTool
@dataclass
class ToolRunComputerAction:
    tool_call: ResponseComputerToolCall
    computer_tool: ComputerTool

class QueueCompleteSentinel: # 队列的空元素?
    pass



class TraceCtxManager:
    """Creates a trace only if there is no current trace, and manages the trace lifecycle."""
    def __enter__(self) -> TraceCtxManager:
        current_trace = get_current_trace()
        if not current_trace:
            self.trace.start(mark_as_current=True)
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.trace.finish(reset_current=True)
