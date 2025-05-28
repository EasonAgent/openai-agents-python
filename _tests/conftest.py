import os
import logging
import pathlib
import dotenv
import pytest
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, Agent

dotenv.load_dotenv(pathlib.Path(__file__).parent / ".env")


@pytest.fixture(scope="session")
def openai_client() -> AsyncOpenAI:
    BASE_URL = os.getenv("OPENAI_BASE_URL") or ""
    API_KEY = os.getenv("OPENAI_API_KEY") or ""
    logging.info(f"> using base_url: {BASE_URL}")
    client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
    return client

@pytest.fixture(scope="session")
def openai_chat_completions_model(openai_client: AsyncOpenAI) -> OpenAIChatCompletionsModel:
    MODEL_NAME = "gpt-4o"
    model = OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=openai_client)
    # model = OpenAIResponsesModel(model=MODEL_NAME, openai_client=client)
    return model

@pytest.fixture()
def agent(openai_chat_completions_model: OpenAIChatCompletionsModel):
    agent = Agent(
        name="Assistant",
        instructions="You are a helpful assistant. be VERY concise.",
        model=openai_chat_completions_model,
    )
    return agent