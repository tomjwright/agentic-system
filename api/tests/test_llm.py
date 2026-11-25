"""Seam 1: the agent's and judge's model settings. Builds clients only; never calls them."""

import logging

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from route_api.llm import models_from_env

KEYS = {"ANTHROPIC_API_KEY": "synthetic-anthropic-key", "GOOGLE_API_KEY": "synthetic-google-key"}


def test_both_keys_build_the_agent_and_judge_models(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)

    models = models_from_env()

    assert models is not None
    assert (models.agent_name, models.judge_name) == (
        "anthropic:claude-haiku-4-5",
        "google_genai:gemini-3.5-flash-lite",
    )
    assert isinstance(models.agent, ChatAnthropic)
    assert models.agent.model == "claude-haiku-4-5"
    assert models.agent.temperature == 0
    assert isinstance(models.judge, ChatGoogleGenerativeAI)
    assert models.judge.model.removeprefix("models/") == "gemini-3.5-flash-lite"
    assert models.judge.temperature == 0


@pytest.mark.parametrize("missing", list(KEYS))
def test_a_missing_key_turns_the_agent_off_and_names_only_the_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, missing: str
) -> None:
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(missing, "")
    caplog.set_level(logging.INFO)

    assert models_from_env() is None
    assert missing in caplog.text
    for value in KEYS.values():
        assert value not in caplog.text


def test_candidate_models_use_their_own_providers_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)

    models = models_from_env("google_genai:gemini-3.5-flash-lite", "anthropic:claude-haiku-4-5")

    assert models is not None
    assert isinstance(models.agent, ChatGoogleGenerativeAI)
    assert models.agent.model.removeprefix("models/") == "gemini-3.5-flash-lite"
    assert isinstance(models.judge, ChatAnthropic)
    assert models.judge_name == "anthropic:claude-haiku-4-5"


def test_a_model_from_an_unknown_provider_is_not_built(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    caplog.set_level(logging.INFO)

    assert models_from_env("openai:gpt-x") is None
    assert "a key for openai:gpt-x" in caplog.text
