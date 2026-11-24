"""The route agent: an explicit LangGraph flow in which every answer is judged.

interpret -> (clarify | generate) -> draft -> judge -> publish, with one repair and a
second judgment when the judge rejects a draft. Code writes the answer itself when no route
was made, a draft is rejected twice or a model is unavailable. Geometry comes only from the
deterministic generator; models read the user's words and measured RouteFacts, never
coordinates, keys or the database.

Adapted from tomjwright/agent-template at commit 5e1068c0bf9872f3482c80a9f36898eb7b531655
(state as a TypedDict, structured model output validated before use, one graph per run).
The routing between nodes is fixed code, not a model, so a run makes at most five model
calls (one reading, two drafts, two judgments) within one time budget.
"""

import time
from typing import Any, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from route_api.agent_models import (
    AgentResult,
    Clarification,
    FallbackReason,
    Interpretation,
    RouteFacts,
    RunRequest,
    Verdict,
)
from route_api.contracts import Distance, DistanceTarget
from route_api.generation import Generation, generate
from route_api.geography import line_length_m
from route_api.heigit import Heigit
from route_api.restrictions import RestrictedWays
from route_api.route_selection import DISTANCE_LIMITS_KM, distance_bounds, outside_activity_limits
from route_api.runs import LIMITATIONS

TIME_BUDGET_S = 90
ACTIVITY_NAMES = {"running": "running", "road_cycling": "road cycling"}

INTERPRET_PROMPT = (
    "You read requests for a running or road-cycling loop in Singapore. Report only what"
    " the user's message states: the activity, the distance (a target or a min-max range in"
    " km) and any other wishes. Leave a field null when the message does not state it."
)
DRAFT_PROMPT = (
    "You write the reply a user sees. State only the facts given, in two or three plain"
    " sentences. Never add distances, times, places, safety, shade or greenery claims that"
    " are not in the facts. Say which wishes are not supported yet."
)
JUDGE_PROMPT = (
    "You check a reply against the facts it must be based on. Reject it if it states"
    " anything the facts do not support, contradicts them, leaves out a limitation that"
    " matters, or claims an unsupported wish was met. List every problem."
)


class RunState(TypedDict, total=False):
    interpretation: Interpretation
    clarification: Clarification
    facts: RouteFacts
    generation: Generation
    draft: str
    verdicts: list[Verdict]
    repairs: int
    message: str
    fallback_reason: FallbackReason


class RouteAgent:
    """One run: its request, models, providers and limits. Built fresh for every run."""

    def __init__(
        self,
        request: RunRequest,
        agent_model: BaseChatModel,
        judge_model: BaseChatModel,
        heigit: Heigit,
        restricted_ways: RestrictedWays,
        time_budget_s: float,
    ):
        self.request = request
        self.agent_model = agent_model
        self.judge_model = judge_model
        self.heigit = heigit
        self.restricted_ways = restricted_ways
        self.deadline = time.monotonic() + time_budget_s

    def graph(self) -> Any:
        graph = StateGraph(RunState)
        graph.add_node(self.interpret)
        graph.add_node(self.generate)
        graph.add_node(self.draft)
        graph.add_node(self.judge)
        graph.add_edge(START, "interpret")
        graph.add_conditional_edges("interpret", self.after_interpret)
        graph.add_conditional_edges("generate", self.after_generate)
        graph.add_conditional_edges("draft", self.after_draft)
        graph.add_conditional_edges("judge", self.after_judge)
        return graph.compile()

    def ask(
        self, model: BaseChatModel, system: str, prompt: str, schema: type[BaseModel] | None
    ) -> Any:
        """One model call. Raises when the time is spent or the reply is invalid."""
        if time.monotonic() >= self.deadline:
            raise TimeoutError
        messages = [SystemMessage(system), HumanMessage(prompt)]
        if schema is None:
            reply = model.invoke(messages).text
            if not reply.strip():
                raise ValueError
            return reply
        return schema.model_validate(model.with_structured_output(schema).invoke(messages))

    def interpret(self, state: RunState) -> RunState:
        request = self.request
        prompt = f"The user's message: {request.brief!r}"
        try:
            interpretation = self.ask(self.agent_model, INTERPRET_PROMPT, prompt, Interpretation)
        except Exception:
            return {"fallback_reason": "interpretation_unavailable"}
        clarification = clarification_needed(request, interpretation)
        if clarification is not None:
            return {"clarification": clarification}
        return {"interpretation": interpretation}

    def after_interpret(self, state: RunState) -> str:
        if "fallback_reason" in state:
            return END
        if "clarification" in state:
            return "draft"
        return "generate"

    def generate(self, state: RunState) -> RunState:
        interpretation = state["interpretation"]
        activity = self.request.activity or interpretation.activity
        distance = self.request.distance or interpretation.distance
        start = self.request.start
        assert activity is not None and distance is not None and start is not None
        bounds = distance_bounds(distance)
        facts = RouteFacts(
            outcome="provider_error",
            activity=activity,
            start_name=start.name,
            min_km=bounds.min_m / 1000,
            max_km=bounds.max_m / 1000,
            tries=0,
            error_code="generation_failed",
            unsupported_preferences=interpretation.preferences,
        )
        try:
            generation = generate(
                self.heigit,
                activity,
                start.coordinates,
                bounds,
                self.restricted_ways,
                max(self.deadline - time.monotonic(), 0),
            )
        except Exception:
            return {"facts": facts, "fallback_reason": "no_route"}
        measure(facts, generation)
        if facts.outcome != "route":
            return {"generation": generation, "facts": facts, "fallback_reason": "no_route"}
        return {"generation": generation, "facts": facts}

    def after_generate(self, state: RunState) -> str:
        if "fallback_reason" in state:
            return END
        return "draft"

    def draft(self, state: RunState) -> RunState:
        prompt = f"Facts: {grounds(state)}"
        if "verdicts" in state:
            problems = "; ".join(state["verdicts"][-1].reasons)
            prompt += f"\nYour last reply: {state['draft']!r}\nThe checker's problems with it: "
            prompt += problems
        try:
            return {"draft": self.ask(self.agent_model, DRAFT_PROMPT, prompt, None)}
        except Exception:
            return {"fallback_reason": "draft_unavailable"}

    def after_draft(self, state: RunState) -> str:
        if "fallback_reason" in state:
            return END
        return "judge"

    def judge(self, state: RunState) -> RunState:
        prompt = f"Facts: {grounds(state)}\nReply to check: {state['draft']!r}"
        try:
            verdict = self.ask(self.judge_model, JUDGE_PROMPT, prompt, Verdict)
        except Exception:
            return {"fallback_reason": "judge_unavailable"}
        verdicts = [*state.get("verdicts", []), verdict]
        if verdict.approved:
            return {"verdicts": verdicts, "message": state["draft"]}
        repairs = state.get("repairs", 0)
        if repairs >= 1:
            return {"verdicts": verdicts, "fallback_reason": "rejected_twice"}
        return {"verdicts": verdicts, "repairs": repairs + 1}

    def after_judge(self, state: RunState) -> str:
        if "message" in state or "fallback_reason" in state:
            return END
        return "draft"


def run_agent(
    request: RunRequest,
    agent_model: BaseChatModel,
    judge_model: BaseChatModel,
    heigit: Heigit,
    restricted_ways: RestrictedWays,
    time_budget_s: float = TIME_BUDGET_S,
) -> AgentResult:
    """Run one request through the graph and return the answer the user may see."""
    agent = RouteAgent(request, agent_model, judge_model, heigit, restricted_ways, time_budget_s)
    state: RunState = agent.graph().invoke({})
    clarification = state.get("clarification")
    facts = state.get("facts")
    message = state.get("message")
    source: Literal["approved_draft", "fallback"] = "approved_draft"
    if message is None:
        message = fallback_message(clarification, facts)
        source = "fallback"
    return AgentResult(
        run_id=request.run_id,
        kind=result_kind(clarification, facts),
        message=message,
        message_source=source,
        fallback_reason=state.get("fallback_reason"),
        clarification=clarification,
        facts=facts,
        generation=state.get("generation"),
        verdicts=state.get("verdicts", []),
        repairs=state.get("repairs", 0),
    )


def clarification_needed(request: RunRequest, heard: Interpretation) -> Clarification | None:
    """What must be asked before a route can be made, or None when nothing is missing."""
    conflicts = []
    if request.activity and heard.activity and request.activity != heard.activity:
        conflicts.append(
            f"the form says {ACTIVITY_NAMES[request.activity]}"
            f" but your message says {ACTIVITY_NAMES[heard.activity]}"
        )
    if request.distance and heard.distance and request.distance != heard.distance:
        conflicts.append(
            f"the form says {distance_text(request.distance)}"
            f" but your message says {distance_text(heard.distance)}"
        )
    if conflicts:
        return Clarification(reason="conflict", details=conflicts)
    activity = request.activity or heard.activity
    distance = request.distance or heard.distance
    if activity is None:
        return Clarification(reason="missing_activity")
    if distance is None:
        return Clarification(reason="missing_distance")
    if request.start is None:
        return Clarification(reason="missing_start")
    if outside_activity_limits(activity, distance):
        lowest_km, highest_km = DISTANCE_LIMITS_KM[activity]
        limit = f"{ACTIVITY_NAMES[activity].capitalize()} loops are {lowest_km} to {highest_km} km"
        return Clarification(reason="distance_out_of_limits", details=[limit])
    return None


def measure(facts: RouteFacts, generation: Generation) -> None:
    """Fill in what the generation measured; only a selected route has a distance."""
    facts.tries = len(generation.attempts)
    facts.error_code = generation.error_code
    if generation.error_code:
        return
    facts.outcome = "no_route"
    if generation.selection is None or generation.selection.chosen is None:
        return
    route = generation.attempts[generation.selection.chosen].route
    assert route is not None
    facts.outcome = "route"
    facts.distance_km = round(line_length_m(route.coordinates) / 1000, 2)
    facts.duration_minutes = round(route.duration_s / 60)
    facts.limitations = list(LIMITATIONS[facts.activity])


def grounds(state: RunState) -> str:
    """What a draft must be based on, as JSON for the models. It holds no coordinates."""
    shown: BaseModel | None = state.get("facts") or state.get("clarification")
    assert shown is not None
    return shown.model_dump_json()


def result_kind(clarification: Clarification | None, facts: RouteFacts | None) -> Any:
    if clarification is not None:
        return "clarification"
    if facts is None or facts.outcome == "provider_error":
        return "failed"
    return facts.outcome


def fallback_message(clarification: Clarification | None, facts: RouteFacts | None) -> str:
    """The answer written by code from the facts alone, used when no draft is approved."""
    if clarification is not None:
        return clarification_message(clarification)
    if facts is None:
        return "The route assistant could not read your request. Please try again."
    if facts.outcome == "provider_error":
        return f"No route could be made: {facts.error_code}."
    name = ACTIVITY_NAMES[facts.activity]
    asked = f"{facts.min_km:.2f}-{facts.max_km:.2f} km"
    if facts.outcome == "no_route":
        sentences = [f"No acceptable {asked} {name} loop was found in {facts.tries} tries."]
    else:
        sentences = [
            f"Here is a {facts.distance_km:.2f} km {name} loop for the {asked} you asked for.",
            *facts.limitations,
        ]
    if facts.unsupported_preferences:
        sentences.append(f"Not supported yet: {', '.join(facts.unsupported_preferences)}.")
    return " ".join(sentences)


def clarification_message(clarification: Clarification) -> str:
    if clarification.reason == "conflict":
        return f"Please clarify: {'; '.join(clarification.details)}."
    if clarification.reason == "missing_activity":
        return "Is this a run or a road-cycling ride?"
    if clarification.reason == "missing_distance":
        return "What distance would you like? Give a target or a range in km."
    if clarification.reason == "missing_start":
        return "Where should the loop start? Search for a place and confirm it first."
    return f"{clarification.details[0]}. What distance would you like?"


def distance_text(distance: Distance) -> str:
    if isinstance(distance, DistanceTarget):
        return f"{distance.target_km:g} km"
    return f"{distance.min_km:g}-{distance.max_km:g} km"
