## Orchestrating

1. 整体来说, 可以分为两种方案: LLM自主 & Orchestrating via code. (案例参见 examples/agent_patterns)
2. 如何让LLM自动决策 (最佳实践)
    - **提示词**: Invest in good prompts. Make it clear what tools are available, how to use them, and what parameters it must operate within.
    - **迭代**: Monitor your app and iterate on it. See where things go wrong, and iterate on your prompts.
    - **自省**: Allow the agent to introspect and improve. For example, run it in a loop, and let it critique itself; or, provide error messages and let it improve.
    - **专业化**: Have specialized agents that excel in one task, rather than having a general purpose agent that is expected to be good at anything.
    - **评估**: Invest in [evals](https://platform.openai.com/docs/guides/evals). This lets you train your agents to improve and get better at tasks.
3. 如何采用固定流程? (类似 Anthropic 那个patterns)
    - **分支**: Using [structured outputs](https://platform.openai.com/docs/guides/structured-outputs) to generate well formed data that you can inspect with your code. For example, you might ask an agent to classify the task into a few categories, and then pick the next agent based on the category.
    - **链式**: Chaining multiple agents by transforming the output of one into the input of the next. You can decompose a task like writing a blog post into a series of steps - do research, write an outline, write the blog post, critique it, and then improve it.
    - **循环**: (例如 gen-eval 迭代) Running the agent that performs the task in a `while` loop with an agent that evaluates and provides feedback, until the evaluator says the output passes certain criteria.
    - **并行**: Running multiple agents in parallel, e.g. via Python primitives like `asyncio.gather`. This is useful for speed when you have multiple tasks that don't depend on each other.
