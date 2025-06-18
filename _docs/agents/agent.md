## Agent
- agent 配置. 包括如下字段:
    - `instructions`: 指令, also known as a developer message or system prompt. 注意可以是函数;
    - `model, model_settings`: 模型配置;
    - `tools`: 工具;
    - `handoffs, handoff_description`: 描述转接列表和被转接的描述;
    - `input_guardrails, output_guardrails`: 输入检查和输出检查;
    - `output_type`: 输出类型, Pydantic 模型;
    - `hooks`: 钩子;
- 相关功能:
    - Context: 用于在agent生命周期中传递数据, 通过 `RunContextWrapper` 包装
    - Output types: 默认为文本, 可以结构化输出
    - Handoffs: 设置agents之间的转接逻辑
    - Dynamic instructions: 可以动态生成 SP!
    - Lifecycle events (hooks)
    - Guardrails
    - Cloning/copying agents: 通过 `clone()` 复制

### 代码
```python
@dataclass
class Agent(Generic[TContext]):
    """An agent is an AI model configured with instructions, tools, guardrails, handoffs and more.

    We strongly recommend passing `instructions`, which is the "system prompt" for the agent. In
    addition, you can pass `handoff_description`, which is a human-readable description of the
    agent, used when the agent is used inside tools/handoffs.

    Agents are generic on the context type. The context is a (mutable) object you create. It is
    passed to tool functions, handoffs, guardrails, etc.
    """

    name: str
    """The name of the agent."""

    instructions: (
        str
        | Callable[
            [RunContextWrapper[TContext], Agent[TContext]],
            MaybeAwaitable[str],
        ]
        | None
    ) = None
    """The instructions for the agent. Will be used as the "system prompt" when this agent is
    invoked. Describes what the agent should do, and how it responds.

    Can either be a string, or a function that dynamically generates instructions for the agent. If
    you provide a function, it will be called with the context and the agent instance. It must
    return a string.
    """

    handoff_description: str | None = None
    """A description of the agent. This is used when the agent is used as a handoff, so that an
    LLM knows what it does and when to invoke it.
    """

    handoffs: list[Agent[Any] | Handoff[TContext]] = field(default_factory=list)
    """Handoffs are sub-agents that the agent can delegate to. You can provide a list of handoffs,
    and the agent can choose to delegate to them if relevant. Allows for separation of concerns and
    modularity.
    """

    model: str | Model | None = None
    """The model implementation to use when invoking the LLM.

    By default, if not set, the agent will use the default model configured in
    `model_settings.DEFAULT_MODEL`.
    """

    model_settings: ModelSettings = field(default_factory=ModelSettings)
    """Configures model-specific tuning parameters (e.g. temperature, top_p).
    """

    tools: list[Tool] = field(default_factory=list)
    """A list of tools that the agent can use."""

    input_guardrails: list[InputGuardrail[TContext]] = field(default_factory=list)
    """A list of checks that run in parallel to the agent's execution, before generating a
    response. Runs only if the agent is the first agent in the chain.
    """

    output_guardrails: list[OutputGuardrail[TContext]] = field(default_factory=list)
    """A list of checks that run on the final output of the agent, after generating a response.
    Runs only if the agent produces a final output.
    """

    output_type: type[Any] | None = None
    """The type of the output object. If not provided, the output will be `str`."""

    hooks: AgentHooks[TContext] | None = None
    """A class that receives callbacks on various lifecycle events for this agent.
    """
```

### Dynamic instructions / Context

```python
def dynamic_instructions(
    context: RunContextWrapper[UserContext], agent: Agent[UserContext]
) -> str:
    return f"The user's name is {context.context.name}. Help them with their questions."


agent = Agent[UserContext](
    name="Triage agent",
    instructions=dynamic_instructions,
)
```


```python
# 例子2: 通过 run_context 获取 context
from agents import Agent, RunContextWrapper, Runner

# 设置动态的 instruction
class CustomContext:
    def __init__(self, style: Literal["haiku", "pirate", "robot"]):
        self.style = style

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

# 创建 agent (传入自定义的 instruction)
agent = Agent(
    name="Chat agent",
    instructions=custom_instructions,
)

# 在 runner 中传入 context
async def main():
    choice: Literal["haiku", "pirate", "robot"] = random.choice(["haiku", "pirate", "robot"])
    context = CustomContext(style=choice)
    print(f"Using style: {choice}\n")

    user_message = "Tell me a joke."
    print(f"User: {user_message}")
    result = await Runner.run(agent, user_message, context=context)

    print(f"Assistant: {result.final_output}")
```
