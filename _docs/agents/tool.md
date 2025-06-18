
## Tool

1. 支持三种类型的工具
    - **官方提供** Hosted tools: these run on LLM servers alongside the AI models. OpenAI offers retrieval, web search and computer use as hosted tools.
    - **函数调用** Function calling: these allow you to use any Python function as a tool.
    - **Agent as tool** Agents as tools: this allows you to use an agent as a tool, allowing Agents to call other agents without handing off to them.
2. 函数范式
    1. 提供一个 `function_schema(func, docstring_style, name_override, description_override, use_docstring_info, strict_json_schema)` 函数
        1. docstring_style: 包括 ["sphinx", "numpy", "google"], 参见 griffe
    2. 转为标准化的 `FuncSchema` 函数定义, 包括
        1. name: str
        2. description: str | None
        3. params_pydantic_model: type[BaseModel]: 通过 `pydantic.create_model` 生成
        4. params_json_schema: dict[str, Any]: 通过 Pydantic model 自动得到
        5. signature: inspect.Signature: 函数签名 (来自 `inspect.signature`)
        6. takes_context: bool = False: 这个函数是否用到了 RunContextWrapper (函数的第一个参数!)
        7. strict_json_schema: bool = True
3. 自动函数范式生成 (function_schema)
    - The signature parsing is done via the `inspect` module. We use type annotations to understand the types for the arguments, and dynamically build a Pydantic model to represent the overall schema. It supports most types, including Python primitives, Pydantic models, TypedDicts, and more.
    - We use `griffe` to parse docstrings. Supported docstring formats are `google`, `sphinx` and `numpy`. We attempt to automatically detect the docstring format, but this is best-effort and you can explicitly set it when calling `function_tool`. You can also disable docstring parsing by setting `use_docstring_info` to `False`.
4. FunctionTool
    1. 一个简单的数据抽象, 包括 name, description, params_json_schema, on_invoke_tool, strict_json_schema 字段
    2. 其中, `on_invoke_tool: Callable[[RunContextWrapper[Any], str], Awaitable[str]]` 即函数调用的实现, 注意其:
        1. 输入: JSON str 形式的参数
        2. 输出: str (结构化输出也转为 str)
    3. 错误处理: (1) 直接 raise, 中断 run; (2) 返回一个 str 交给LLM来处理
5. Agent as tool: 通过 `.as_tool(tool_name, tool_description, custom_output_extractor)` 来转为工具
    1. Agent as tool 和 handoff 有什么区别? 
        1. 输入: handoff 接收 conversation history, 而 tool 的输入是LLM生成的;
        2. 会话控制: handoff 会接管会话, 而 tool 只是作为工具调用, 会话权仍在原本的agent手上;
    2. 实现机制: 本质上都是 FunctionTool, 通过 functions_tool 工具将 Runner 流程转为函数调用
    3. 结果处理: 支持传入一个 `custom_output_extractor` 来处理agents的输出
6. 错误处理
    1. 提供一个 `failure_error_function` 来处理函数错误, 类型为 `ToolErrorFunction = Callable[[RunContextWrapper[Any], Exception], MaybeAwaitable[str]]`
    2. 默认为 `default_tool_error_function(ctx: RunContextWrapper[Any], error: Exception) -> str:`, 直接将在 str(error) 之间加一段文字 (来交给LLM处理) -- 当然会有 tracing 机制
7. LLM如何使用tools? 
    1. 对于 chat.complete API, 转为 `ChatCompletionToolParam`, 
        1. 也即 {"type": "function", "function": {"name": str, "description": str, "parameters": dict[str, Any]}}
    2. 对于 responses API, 模型调用包括 include/tools 两个参数, 其中工具类型为 `ToolParam: TypeAlias = Union[FileSearchToolParam, FunctionToolParam, ComputerToolParam, WebSearchToolParam]`
        1. `FunctionToolParam`: 也即 {"type": "function", "name": str, "description": str, "parameters": dict[str, object], "strict": bool}
        2. 特殊工具: type=web_search_preview|file_search|computer_use_preview, 不定义name/description, 有展开的parameters
    3. LLM的输入: 都是 `FunctionTool` 中的3个字段: name, description, params_json_schema
8. MCP
    1. 就是正常的工具定义, 通过 `mcp_servers: list[MCPServer]` 参数传入 Agent 定义中
    2. NOTE: 在框架中仅暴露 `list_tools` 工具!
        1. 和正常的 function tool 一样! 通过 `MCPUtil.to_function_tool` 转换
        2. 在引入 Agent 前后, 需要手动控制 `MCPServer` 的 connect/cleanup!!

