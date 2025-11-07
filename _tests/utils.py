import os
import logging
import pathlib
import dotenv
from openai import AsyncOpenAI
from agents import ItemHelpers, RunResultStreaming, OpenAIChatCompletionsModel, Agent

dotenv.load_dotenv(pathlib.Path(__file__).parent / ".env")


def get_openai_chat_completions_model(base_url: str=None, api_key: str=None, model_name: str=None) -> OpenAIChatCompletionsModel:
    base_url = base_url or os.getenv("CUSTOM_BASE_URL") or ""
    api_key = api_key or os.getenv("CUSTOM_API_KEY") or ""
    model_name = model_name or os.getenv("CUSTOM_MODEL_NAME") or ""
    logging.info(f"> using {model_name} from {base_url}")
    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    model = OpenAIChatCompletionsModel(model=model_name, openai_client=client)
    return model

def get_agent(model: OpenAIChatCompletionsModel) -> Agent:
    agent = Agent(
        name="Assistant",
        instructions="You are a helpful assistant. be VERY concise.",
        model=model,
    )
    return agent

# from https://openai.github.io/openai-agents-python/streaming/
async def print_stream_events(result: RunResultStreaming):
    print("=== Run starting ===")
    async for event in result.stream_events():
        # We'll ignore the raw responses event deltas
        if event.type == "raw_response_event":
            continue
        # When the agent updates, print that
        elif event.type == "agent_updated_stream_event":
            print(f"Agent updated: {event.new_agent.name}")
            continue
        # When items are generated, print them
        elif event.type == "run_item_stream_event":
            if event.item.type == "tool_call_item":
                print("-- Tool was called")
            elif event.item.type == "tool_call_output_item":
                print(f"-- Tool output: {event.item.output}")
            elif event.item.type == "message_output_item":
                print(f"-- Message output:\n {ItemHelpers.text_message_output(event.item)}")
            else:
                pass  # Ignore other event types
    print("=== Run complete ===")