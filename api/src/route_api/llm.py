"""The agent's and the judge's chat models, each built from its own settings.

Adapted from tomjwright/agent-template's llm.py (commit 5e1068c0bf9872f3482c80a9f36898eb7b531655):
a "provider:model" spec handed to init_chat_model at temperature 0. Here the agent and the
judge have separate specs (AGENT_MODEL, JUDGE_MODEL) and each provider's key must be set,
or the route agent is off and its endpoint answers 503. Keys are read here and passed only
to the model client; they are never logged.
"""

import os
from dataclasses import dataclass

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from route_api.logs import log_event


@dataclass
class Models:
    agent: BaseChatModel
    judge: BaseChatModel
    agent_name: str
    judge_name: str


AGENT_MODEL = "anthropic:claude-haiku-4-5"
AGENT_KEY = "ANTHROPIC_API_KEY"
JUDGE_MODEL = "google_genai:gemini-3.5-flash"
JUDGE_KEY = "GOOGLE_API_KEY"


def models_from_env() -> Models | None:
    """Both models when ANTHROPIC_API_KEY and GOOGLE_API_KEY are set, else None."""
    agent_key = os.environ.get(AGENT_KEY)
    judge_key = os.environ.get(JUDGE_KEY)
    for name, key in [(AGENT_KEY, agent_key), (JUDGE_KEY, judge_key)]:
        if not key:
            log_event("agent_not_configured", missing=name)
            return None
    agent = init_chat_model(AGENT_MODEL, temperature=0, api_key=agent_key)
    judge = init_chat_model(JUDGE_MODEL, temperature=0, api_key=judge_key)
    return Models(agent=agent, judge=judge, agent_name=AGENT_MODEL, judge_name=JUDGE_MODEL)
