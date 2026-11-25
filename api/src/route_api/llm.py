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
JUDGE_MODEL = "google_genai:gemini-3.5-flash"
PROVIDER_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "google_genai": "GOOGLE_API_KEY"}


def models_from_env(agent_spec: str = AGENT_MODEL, judge_spec: str = JUDGE_MODEL) -> Models | None:
    """Both models when their providers' keys are set, else None. The evals pass other specs
    to compare candidate models."""
    keys = []
    for spec in [agent_spec, judge_spec]:
        name = PROVIDER_KEYS.get(spec.split(":")[0], f"a key for {spec}")
        key = os.environ.get(name)
        if not key:
            log_event("agent_not_configured", missing=name)
            return None
        keys.append(key)
    agent = init_chat_model(agent_spec, temperature=0, api_key=keys[0])
    judge = init_chat_model(judge_spec, temperature=0, api_key=keys[1])
    return Models(agent=agent, judge=judge, agent_name=agent_spec, judge_name=judge_spec)
