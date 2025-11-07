from agents import Agent, Runner
from utils import print_stream_events, get_openai_chat_completions_model, get_agent


async def test_long_input():
    query = "who was the first president of the united states? "  # 10 tokens
    query *= 20_000  # 200k
    
    model = get_openai_chat_completions_model()
    agent = get_agent(model)
    result = Runner.run_streamed(agent, input=query)
    await print_stream_events(result)

