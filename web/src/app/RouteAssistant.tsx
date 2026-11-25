"use client";

import { useState } from "react";

import { type AgentAnswer, type AgentStep, ApiError, askAssistant, type Distance } from "@/api";

type Props = {
  routeRequestId: string;
  distance: Distance | null;
  // Called once an answer arrives, with its stored run or null; a failed ask keeps the current route.
  onRun: (generationRunId: string | null) => void;
};

function distanceText(distance: Distance): string {
  if (distance.kind === "target") {
    return `about ${distance.target_km} km`;
  }
  return `${distance.min_km}-${distance.max_km} km`;
}

function stepText(step: AgentStep): string {
  const reason = (step.reason ?? "").replaceAll("_", " ");
  if (step.name === "read_request") {
    return "Read your message";
  }
  if (step.name === "asked_clarification") {
    return `Asked you to clarify: ${reason}`;
  }
  if (step.name === "generated_route") {
    if (step.tries === 0) {
      return "Could not get a loop from HeiGIT";
    }
    return `Tried ${step.tries} ${step.tries === 1 ? "loop" : "loops"} from HeiGIT`;
  }
  if (step.name === "drafted") {
    return "Drafted an answer";
  }
  if (step.name === "judged") {
    return step.approved ? "Judge approved it" : "Judge rejected it";
  }
  if (step.name === "repaired") {
    return "Redrafted it with the judge's problems";
  }
  if (step.reason === "no_route") {
    return "No loop was accepted, so it answered from the measured facts";
  }
  return `Answered from the measured facts instead: ${reason}`;
}

export default function RouteAssistant({ routeRequestId, distance, onRun }: Props) {
  const [brief, setBrief] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<AgentAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notSetUp, setNotSetUp] = useState(false);
  const clarifying = answer?.run.kind === "clarification";

  async function ask() {
    if (brief.trim() === "") {
      setError("Type what you would like first.");
      return;
    }
    setAsking(true);
    setError(null);
    setAnswer(null);
    try {
      const found = await askAssistant(routeRequestId, brief.trim(), distance);
      setAnswer(found);
      // Each message is read on its own, so a question leaves the message there to edit.
      if (found.run.kind !== "clarification") {
        setBrief("");
      }
      onRun(found.run.generation_run_id);
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "agent_not_configured") {
        setNotSetUp(true);
      } else if (caught instanceof ApiError) {
        setError(caught.message);
      } else {
        setError("The route API could not be reached.");
      }
    } finally {
      setAsking(false);
    }
  }

  if (notSetUp) {
    return (
      <div className="assistant">
        <p className="status">
          The route assistant is not set up here. Generate loop above still works.
        </p>
      </div>
    );
  }

  return (
    <div className="assistant">
      <label>
        {clarifying ? "Edit your message" : "Ask the route assistant"}
        <textarea
          value={brief}
          onChange={(event) => setBrief(event.target.value)}
          rows={3}
          maxLength={1000}
          placeholder="e.g. an easy 5k run"
        />
      </label>
      <p className="address">
        {clarifying &&
          "It reads each message on its own, so include everything again." +
            " If the form and your message disagree, change one of them. "}
        It starts from your confirmed start.{" "}
        {distance
          ? `The form's distance (${distanceText(distance)}) is sent with your message.`
          : "Say the distance in your message."}
      </p>
      <button type="button" className="confirm" onClick={ask} disabled={asking}>
        {clarifying ? "Ask again" : "Ask"}
      </button>
      {asking && (
        <p className="status" role="status">
          Asking the route assistant: one request that reads your message, may make a loop and
          has its answer checked before you see it. It can take a minute or two.
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
        </div>
      )}
    </div>
  );
}
