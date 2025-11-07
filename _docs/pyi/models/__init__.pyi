from collections.abc import Iterable
from typing import Any, Literal, cast

from openai import NOT_GIVEN, NotGiven
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionContentPartImageParam,
    ChatCompletionContentPartParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionDeveloperMessageParam,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolChoiceOptionParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam
from openai.types.chat.completion_create_params import ResponseFormat
from openai.types.responses import (
    EasyInputMessageParam,
    ResponseFileSearchToolCallParam,
    ResponseFunctionToolCall,
    ResponseFunctionToolCallParam,
    ResponseInputContentParam,
    ResponseInputImageParam,
    ResponseInputTextParam,
    ResponseOutputMessage,
    ResponseOutputMessageParam,
    ResponseOutputRefusal,
    ResponseOutputText,
)
from openai.types.responses.response_input_param import FunctionCallOutput, ItemReference, Message

from ..agent import AgentOutputSchemaBase
from ..tool import Handoff, Tool
from ..item import TResponseOutputItem


# agents/models/chatcmpl_converter.py
class Converter:
    # 以下均为 @classmethod
    def convert_tool_choice(cls, tool_choice: Literal["auto", "required", "none"] | str | None) -> ChatCompletionToolChoiceOptionParam | NotGiven:
        """  """
    def convert_response_format(cls, final_output_schema: AgentOutputSchemaBase | None) -> ResponseFormat | NotGiven:
        """  """
    def message_to_output_items(cls, message: ChatCompletionMessage) -> list[TResponseOutputItem]:
        """  """
    def maybe_easy_input_message(cls, item: Any) -> EasyInputMessageParam | None:
        """  """
    def maybe_input_message(cls, item: Any) -> Message | None:
        """  """
    def maybe_file_search_call(cls, item: Any) -> ResponseFileSearchToolCallParam | None:
        """  """
    def maybe_function_tool_call(cls, item: Any) -> ResponseFunctionToolCallParam | None:
        """  """
    def maybe_function_tool_call_output(cls, item: Any) -> FunctionCallOutput | None:
        """  """
    def maybe_item_reference(cls, item: Any) -> ItemReference | None:
        """  """
    def maybe_response_output_message(cls, item: Any) -> ResponseOutputMessageParam | None:
        """  """
    def extract_text_content(cls, message: ChatCompletionMessage) -> str | list[ChatCompletionContentPartTextParam]:
        """  """
    def extract_all_content(cls, message: ChatCompletionMessage) -> str | list[ChatCompletionContentPartParam]:
        """  """
    def items_to_messages(cls, items: list[TResponseOutputItem]) -> list[ChatCompletionMessageParam]:
        """  """
    def tool_to_openai(cls, tool: Tool) -> ChatCompletionToolParam:
        """  """
    def convert_handoff_tool(cls, handoff: Handoff[Any]) -> ChatCompletionToolParam:
        """  """
