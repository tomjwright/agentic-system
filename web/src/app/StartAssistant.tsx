"use client";

import { useState } from "react";

import {
  type AgentAnswer,
  ApiError,
  askAssistant,
  askAssistantWithoutStart,
  type Candidate,
  createRouteRequest,
  getRouteRequest,
  getRun,
  getSelectedRoute,
  type RouteRequest,
  type SelectedRoute,
} from "@/api";

import { stepText } from "./RouteAssistant";
import type { FirstAnswer } from "./RunPanel";

type Props = {
  // Called once a clicked match is the confirmed start and the assistant has answered on it.
  onConfirmed: (routeRequest: RouteRequest, candidate: Candidate, first: FirstAnswer) => void;
};

function describeError(caught: unknown): string {
  if (caught instanceof ApiError) {
    return caught.message;
  }
  return "The route API could not be reached.";
}

// The route assistant before a start is confirmed. It lists every place the message's start
// matches as a button and makes no route until one is clicked.
export default function StartAssistant({ onConfirmed }: Props) {
  const [brief, setBrief] = useState("");
  const [asked, setAsked] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<AgentAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notSetUp, setNotSetUp] = useState(false);
  const choices = answer?.start_choices ?? null;
  const clarifying = answer?.run.kind === "clarification";

  async function ask() {
    if (brief.trim() === "") {
      setError("Type what you would like first.");
      return;
    }
    setBusy(true);
    setError(null);
    setAnswer(null);
    try {
      setAnswer(await askAssistantWithoutStart(brief.trim()));
      setAsked(brief.trim());
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "agent_not_configured") {
        setNotSetUp(true);
      } else {
        setError(describeError(caught));
      }
    } finally {
      setBusy(false);
    }
  }

  // The clicked match becomes the confirmed start. Only then is the same message asked again,
  // now from that start, which is when a route is made.
  async function choose(candidate: Candidate) {
    if (choices === null) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const start = { kind: "named" as const, query: choices.query, source_id: candidate.source_id };
      const created = await createRouteRequest({ activity: choices.activity, start });
      const routeRequest = await getRouteRequest(created.id);
      const routed = await askAssistant(created.id, asked, null);
      const runId = routed.run.generation_run_id;
      let run = null;
      let route: SelectedRoute | null = null;
      if (runId !== null) {
        run = await getRun(runId);
        if (run.status === "succeeded") {
          route = await getSelectedRoute(runId);
        }
      }
      onConfirmed(routeRequest, candidate, { answer: routed, run, route });
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  if (notSetUp) {
    return (
      <div className="assistant start-assistant">
        <p className="status">The route assistant is not set up here. Search for a start above.</p>
      </div>
    );
  }

  return (
    <div className="assistant start-assistant">
      <label>
        {clarifying ? "Edit your message" : "Or ask the route assistant"}
        <textarea
          value={brief}
          onChange={(event) => setBrief(event.target.value)}
          rows={3}
          maxLength={1000}
          placeholder="e.g. a 5k run from Avenue South Residence"
        />
      </label>
      <p className="address">
        Name your start, the activity and the distance. It lists every place your start matches
        and makes no route until you pick one.
      </p>
      <button type="button" className="confirm" onClick={ask} disabled={busy}>
        {clarifying ? "Ask again" : "Ask"}
      </button>
      {busy && (
        <p className="status" role="status">
          Asking the route assistant. It can take a minute or two.
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {answer && (
        <div className="answer">
          <p>{answer.message}</p>
          <ol aria-label="Assistant steps">
            {answer.steps.map((step, position) => (
              <li key={position}>{stepText(step)}</li>
            ))}
          </ol>
          {choices && (
            <ul className="candidates" aria-label="Starts the assistant found">
              {choices.candidates.map((candidate) => (
                <li key={candidate.source_id}>
                  <button type="button" onClick={() => choose(candidate)} disabled={busy}>
                    <strong>{candidate.name}</strong>
                    <span>{candidate.address}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
