
## Model

### 概述
1. 提供简单的抽象层 `Model`, 只封装 `get_response` 和 `stream_response`，
    1. 对于非流式, `ModelResponse`: 标准化的返回结果, 包括 `output`, `usage`, `referenceable_id`
    2. 对于流式, `TResponseStreamEvent`: 流式返回结果
2. 两者包括相同的参数
    1. `system_instructions`: 系统指令
    2. `input`: 输入
    3. `model_settings`: 模型设置
    4. `tools`: 工具
    5. `output_schema`: 输出模式
    6. `handoffs`: agents 转接
    7. `tracing`: 跟踪
3. 官方针对 ChatCompletions 和 Responses 提供了相应实现. 
    1. 相较于基础版本, responses 版本实现了内置的工具? `file_search, web_search_preview, computer_use_preview`
        responses 接口中还新增了 `includes` 参数

```python
class Model(abc.ABC):
    """The base interface for calling an LLM."""
    @abc.abstractmethod
    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
    ) -> ModelResponse:
        """Get a response from the model.

        Args:
            system_instructions: The system instructions to use.
            input: The input items to the model, in OpenAI Responses format.
            model_settings: The model settings to use.
            tools: The tools available to the model.
            output_schema: The output schema to use.
            handoffs: The handoffs available to the model.
            tracing: Tracing configuration.

        Returns:
            The full model response.
        """
        pass

    @abc.abstractmethod
    def stream_response(...
    ) -> AsyncIterator[TResponseStreamEvent]:
        """Stream a response from the model.
        Returns:
            An iterator of response stream events, in OpenAI Responses format.
        """
        pass
```

### 如何自定义 LLM providers (Tracing)

1. 对于模型provider的配置, 提供了三种方案 (不同的层级):
    1. global: 通过 `set_default_openai_client` 设置默认的 OpenAI client
    2. config: 在 Runner过程中, 配置 `RunConfig` 的 `model_provider`
    3. agent: 在 Agent中, 直接指定 `model` 为 OpenAIChatCompletionsModel/OpenAIResponsesModel -- 可以为不同的agent指定不同的provider
2. 设置 chat.complete/reponse 接口: `set_default_openai_api`
3. 设置 tracing (针对 OpenAI 官方提供的tracing方案)
    1. `set_tracing_disabled`: 禁用 tracing
    2. `set_tracing_export_api_key`: 设置用于tracing 的 API key
    3. 注: 也可以使用第三方的tracing, 见下

```python
# op1: set_default_openai_client
from openai import AsyncOpenAI
from agents import set_default_openai_client, set_default_openai_api, set_tracing_disabled

client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
)
set_default_openai_client(client=client, use_for_tracing=False)
set_default_openai_api("chat_completions")
set_tracing_disabled(disabled=True)

agent = Agent(... model=MODEL_NAME) # 直接指定 model名字即可
```

```python
# op2: ModelProvider in RunConfig
from agents import ModelProvider

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
class CustomModelProvider(ModelProvider):
    def get_model(self, model_name: str | None) -> Model:
        return OpenAIChatCompletionsModel(model=model_name or MODEL_NAME, openai_client=client)
CUSTOM_MODEL_PROVIDER = CustomModelProvider()

agent = Agent(...) # agent 部分正常定义即可
result = await Runner.run(
    agent,
    "What's the weather in Tokyo?",
    run_config=RunConfig(model_provider=CUSTOM_MODEL_PROVIDER), # 在 RunConfig中自定义个 provider
)
```

```python
# op3: 直接指定 model 为特定 OpenAIChatCompletionsModel/OpenAIResponsesModel
client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
agent = Agent(
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    ...
)
```


### OpenAIResponsesModel

```python
class OpenAIResponsesModel(Model):
    """
    Implementation of `Model` that uses the OpenAI Responses API.
    """

    def __init__(
        self,
        model: str | ChatModel,
        openai_client: AsyncOpenAI,
    ) -> None:
        self.model = model
        self._client = openai_client
    
    async def get_response(...) -> ModelResponse:
        # 0. trace 环境
        with response_span(disabled=tracing.is_disabled()) as span_response:
            try:
                # 1. 调用 API & logging
                response = await self._fetch_response(...) # 通过 responses API 来调用
                logger.debug(
                    "LLM resp:\n"
                    f"{json.dumps([x.model_dump() for x in response.output], indent=2)}\n"
                )
                # 2. 计算 usage
                usage = (...)
                # 3. trace
                if tracing.include_data():
                    span_response.span_data.response = response
                    span_response.span_data.input = input
            except Exception as e:
                # 4. 错误处理: tracing & logging
                span_response.set_error(
                    SpanError(
                        message="Error getting response",
                        data={
                            "error": str(e) if tracing.include_data() else e.__class__.__name__,
                        },
                    )
                )
                request_id = e.request_id if isinstance(e, APIStatusError) else None
                logger.error(f"Error getting response: {e}. (request_id: {request_id})")
                raise
        # 5. 组织返回结果
        return ModelResponse(
            output=response.output,
            usage=usage,
            referenceable_id=response.id,
        )
```

```python
    async def _fetch_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
        stream: Literal[True] | Literal[False] = False,
    ) -> Response | AsyncStream[ResponseStreamEvent]:
        list_input = ItemHelpers.input_to_new_input_list(input)

        tool_choice = Converter.convert_tool_choice(model_settings.tool_choice)
        converted_tools = Converter.convert_tools(tools, handoffs)
        response_format = Converter.get_response_format(output_schema)

        logger.debug(
            f"Calling LLM {self.model} with input:\n"
            f"{json.dumps(list_input, indent=2)}\n"
            f"Tools:\n{json.dumps(converted_tools.tools, indent=2)}\n"
            f"Stream: {stream}\n"
            f"Tool choice: {tool_choice}\n"
            f"Response format: {response_format}\n"
        )

        return await self._client.responses.create(
            instructions=self._non_null_or_not_given(system_instructions),
            model=self.model,
            input=list_input,
            include=converted_tools.includes,
            tools=converted_tools.tools,
            temperature=self._non_null_or_not_given(model_settings.temperature),
            top_p=self._non_null_or_not_given(model_settings.top_p),
            truncation=self._non_null_or_not_given(model_settings.truncation),
            max_output_tokens=self._non_null_or_not_given(model_settings.max_tokens),
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
            stream=stream,
            extra_headers=_HEADERS,
            text=response_format,
        )
```

### Converter

```python
class Converter:
    @classmethod
    def convert_tools(
        cls,
        tools: list[Tool],
        handoffs: list[Handoff[Any]],
    ) -> ConvertedTools:
        converted_tools: list[ToolParam] = []
        includes: list[IncludeLiteral] = []

        computer_tools = [tool for tool in tools if isinstance(tool, ComputerTool)]
        if len(computer_tools) > 1:
            raise UserError(f"You can only provide one computer tool. Got {len(computer_tools)}")

        for tool in tools:
            converted_tool, include = cls._convert_tool(tool)
            converted_tools.append(converted_tool)
            if include:
                includes.append(include)

        for handoff in handoffs:
            converted_tools.append(cls._convert_handoff_tool(handoff))

        return ConvertedTools(tools=converted_tools, includes=includes)

    @classmethod
    def _convert_handoff_tool(cls, handoff: Handoff) -> ToolParam: # 返回 reponses 定义的 工具参数
        return {
            "name": handoff.tool_name,
            "parameters": handoff.input_json_schema,
            "strict": handoff.strict_json_schema,
            "type": "function",
            "description": handoff.tool_description,
        }
```


