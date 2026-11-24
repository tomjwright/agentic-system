"""A chat model that answers from a script, so agent tests never call an LLM.

Adapted from agent-template's tests/conftest.py FakeModel (commit 5e1068c). Each call,
plain or through `with_structured_output`, takes the next scripted reply; an exception
in the script is raised instead, like a provider outage.
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import Field


class FakeModel(BaseChatModel):
    replies: list[Any] = Field(default_factory=list)
    prompts: list[str] = Field(default_factory=list)
    schemas: list[Any] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> ChatResult:
        reply = self.next_reply(messages[-1].text)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=reply))])

    def with_structured_output(
        self, schema: dict[str, Any] | type, *, include_raw: bool = False, **kwargs: Any
    ) -> Runnable[Any, Any]:
        self.schemas.append(schema)
        return RunnableLambda(self.next_reply)

    def next_reply(self, prompt: Any) -> Any:
        self.prompts.append(str(prompt))
        if not self.replies:
            raise AssertionError("FakeModel ran out of replies")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
