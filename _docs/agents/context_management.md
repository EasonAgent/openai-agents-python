## Context management

- 区分两种 "context" (概念界定)
    - **应用层**: Context available locally to your code: this is data and dependencies you might need when tool functions run, during callbacks like on_handoff, in lifecycle hooks, etc.
    - **模型层**: Context available to LLMs: this is data the LLM sees when generating a response.
- agents 框架中的 context
    - 属于 Local context (应用层)
    - 使用方式
        - **context的数据定义**: You create any Python object you want. A common pattern is to use a `dataclass` or a `Pydantic` object.
        - **在runner中传入context实例**: You pass that object to the various run methods (e.g. `Runner.run(..., **context=whatever**)`).
        - **在tool/lifecycle hooks中使用wrapper**: All your tool calls, lifecycle hooks etc will be passed a wrapper object, `RunContextWrapper[T]`, where `T` represents your context object type which you can access via `wrapper.context`.
    - 注意, 在agent的生命周期中, **every agent, tool function, lifecycle** 所接受的context应该是相同类型的! 
- 应用场景:
    1. **上下文数据** (关联LLM context): Contextual data for your run (e.g. things like a username/uid or other information about the user)
    2. **依赖** (Dependencies): Dependencies (e.g. logger objects, data fetchers, etc)
    3. **辅助函数** (Helper functions)
- 案例
    - **动态instructions**: 在agent中传入 `instructions=custom_instructions` 方法来自定义动态指令 (例如传入user信息和date)
    - **在工具中使用**: 获取context中的数据 -- 应该是应用最多的场景?
    - **在hooks中使用**: 例如单影 context_wrapper.usage 中的LLM调用情况
- `RunContextWrapper`: 对于用于定义的context的简单封装 (目的是方便tracing/logging)
    - 简单封装自定义的context类. 包括 context, usage 两个属性
    - 其中, usage记录LLM使用情况, 仅仅在 `Runner._get_new_response()` 中使用

### 应用案例

#### 基础场景: 在工具中使用
```python
# https://openai.github.io/openai-agents-python/context/
from agents import Agent, RunContextWrapper, Runner, function_tool

# 1. 定义 Context 数据类别
@dataclass
class UserInfo:
    name: str
    uid: int

# 1.2. 定义工具函数
@function_tool
async def fetch_user_age(wrapper: RunContextWrapper[UserInfo]) -> str:  # 接收 context
    return f"User {wrapper.context.name} is 47 years old"

async def main():
    user_info = UserInfo(name="John", uid=123)  # 1.3 实例

    # 2. 传给 Agent 
    agent = Agent[UserInfo](
        name="Assistant",
        tools=[fetch_user_age],
    )

    # 3. 传给 Runner
    result = await Runner.run(
        starting_agent=agent,
        input="What is the age of the user?",
        context=user_info,
    )

    print(result.final_output)  
    # The user John is 47 years old.
```

#### custom instruction
```python
# examples/basic/dynamic_system_prompt.py
class CustomContext:
    def __init__(self, style: Literal["haiku", "pirate", "robot"]):
        self.style = style

# 1. 定义一个SP处理函数
def custom_instructions(
    run_context: RunContextWrapper[CustomContext], agent: Agent[CustomContext]
) -> str:
    context = run_context.context
    if context.style == "haiku":
        return "Only respond in haikus."
    elif context.style == "pirate":
        return "Respond as a pirate."
    else:
        return "Respond as a robot and say 'beep boop' a lot."

# 2. 传给 Agent
agent = Agent(
    name="Chat agent",
    instructions=custom_instructions,
)

# 3. Runner 中传入实例
result = await Runner.run(agent, user_message, context=context)
```

#### tool

```python
# tests/test_function_tool_decorator.py
@function_tool
async def async_with_context(ctx: RunContextWrapper[DummyContext], prefix: str, num: int) -> str:
    await asyncio.sleep(0)
    return f"{prefix}-{num}-{ctx.context.data}" # 在工具中使用 context 里面的内容

@pytest.mark.asyncio
async def test_async_with_context_invocation():
    tool = async_with_context
    input_data = {"prefix": "Value", "num": 42}
    output = await tool.on_invoke_tool(ctx_wrapper(), json.dumps(input_data)) # 注: 这里的 ctx_wrapper 简单返回一个 DummyContext
    assert output == "Value-42-something"

# 补充: ctx_wrapper
class DummyContext:
    def __init__(self):
        self.data = "something"
def ctx_wrapper() -> RunContextWrapper[DummyContext]:
    return RunContextWrapper(DummyContext())
```

#### RunHooks
- 一个简单的例子: 在 lifecycle 每一步中打印LLM调用情况. 

```python
# examples/basic/lifecycle_example.py
class ExampleHooks(RunHooks):
    def _usage_to_str(self, usage: Usage) -> str:  # 格式化LLM调用情况
        return f"{usage.requests} requests, {usage.input_tokens} input tokens, {usage.output_tokens} output tokens, {usage.total_tokens} total tokens"

    # 事件处理
    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:
        self.event_counter += 1
        print(f"### {self.event_counter}: Agent {agent.name} started. Usage: {self._usage_to_str(context.usage)}")
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:
    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str) -> None:
    async def on_handoff(self, context: RunContextWrapper, from_agent: Agent, to_agent: Agent) -> None:

hooks = ExampleHooks()
await Runner.run(.., hooks=hooks)
```


### RunContextWrapper

```python
# src/agents/run_context.py
from dataclasses import dataclass, field
from typing import Any, Generic
from typing_extensions import TypeVar
from .usage import Usage
TContext = TypeVar("TContext", default=Any)
@dataclass
class RunContextWrapper(Generic[TContext]):
    """This wraps the context object that you passed to `Runner.run()`. It also contains
    information about the usage of the agent run so far.

    NOTE: Contexts are not passed to the LLM. They're a way to pass dependencies and data to code
    you implement, like tool functions, callbacks, hooks, etc.
    """

    context: TContext
    """The context object (or None), passed by you to `Runner.run()`"""

    usage: Usage = field(default_factory=Usage)
    """The usage of the agent run so far. For streamed responses, the usage will be stale until the
    last chunk of the stream is processed.
    """
```


