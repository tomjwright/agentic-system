"use client";

import { useState } from "react";

import {
  ApiError,
  type Distance,
  type GenerationRun,
  getRun,
  getSelectedRoute,
  gpxUrl,
  type RouteRequest,
  type SelectedRoute,
  startRun,
} from "@/api";

const MIN_KM = 1;
const MAX_KM = 50;
const POLL_MS = 2000;

type Props = {
  routeRequest: RouteRequest;
  onRoute: (coordinates: [number, number][] | null) => void;
};

function km(metres: number): string {
  return `${(metres / 1000).toFixed(2)} km`;
}

function minutes(seconds: number): string {
  return `${Math.round(seconds / 60)} min`;
}

function readDistance(mode: string, target: string, low: string, high: string): Distance | string {
  if (mode === "target") {
    const targetKm = Number(target);
    if (!Number.isFinite(targetKm) || targetKm < MIN_KM || targetKm > MAX_KM) {
      return `Enter a distance from ${MIN_KM} to ${MAX_KM} km.`;
    }
    return { kind: "target", target_km: targetKm };
  }
  const minKm = Number(low);
  const maxKm = Number(high);
  if (!Number.isFinite(minKm) || !Number.isFinite(maxKm) || minKm < MIN_KM || maxKm > MAX_KM) {
    return `Enter both ends of the range, from ${MIN_KM} to ${MAX_KM} km.`;
  }
  if (minKm >= maxKm) {
    return "The lower end of the range must be below the upper end.";
  }
  return { kind: "range", min_km: minKm, max_km: maxKm };
}

export default function RunPanel({ routeRequest, onRoute }: Props) {
  const [mode, setMode] = useState("target");
  const [target, setTarget] = useState("5");
  const [low, setLow] = useState("");
  const [high, setHigh] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [run, setRun] = useState<GenerationRun | null>(null);
  const [route, setRoute] = useState<SelectedRoute | null>(null);
  // Kept after a lost response, so "Generate" again resolves to the run already recorded.
  const [pending, setPending] = useState<{ key: string; operationId: string } | null>(null);

  async function generate() {
    const distance = readDistance(mode, target, low, high);
    if (typeof distance === "string") {
      setError(distance);
      return;
    }
    const key = JSON.stringify(distance);
    let operationId = crypto.randomUUID();
    if (pending !== null && pending.key === key) {
      operationId = pending.operationId;
    }
    setPending({ key, operationId });
    setGenerating(true);
    setError(null);
    setRun(null);
    setRoute(null);
    onRoute(null);
    try {
      let found = await startRun(routeRequest.id, operationId, distance);
      while (found.status === "generating") {
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
        found = await getRun(found.id);
      }
      setPending(null);
      setRun(found);
      if (found.status === "succeeded") {
        const selected = await getSelectedRoute(found.id);
        setRoute(selected);
        onRoute(selected.geometry.coordinates);
      }
    } catch (caught) {
      if (caught instanceof ApiError) {
        setPending(null);
        setError(caught.message);
      } else {
        setError("The route API could not be reached. Generate again to pick up the same run.");
      }
    } finally {
      setGenerating(false);
    }
  }

  if (routeRequest.activity !== "running") {
    return <p className="status">Road-cycling loops come in a later version.</p>;
  }

  return (
    <div className="run">
      <h2>Running loop</h2>
      <fieldset>
        <legend>Distance</legend>
        <label>
          <input
            type="radio"
            name="distance-mode"
            checked={mode === "target"}
            onChange={() => setMode("target")}
          />
          About (±10%)
        </label>
        <label>
          <input
            type="radio"
            name="distance-mode"
            checked={mode === "range"}
            onChange={() => setMode("range")}
          />
          Exact range
        </label>
      </fieldset>
      {mode === "target" ? (
        <label className="distance">
          Target km
          <input
            type="number"
            inputMode="decimal"
            min={MIN_KM}
            max={MAX_KM}
            step="0.1"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
          />
        </label>
      ) : (
        <div className="distance-range">
          <label className="distance">
            From km
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              value={low}
              onChange={(event) => setLow(event.target.value)}
            />
          </label>
          <label className="distance">
            To km
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              value={high}
              onChange={(event) => setHigh(event.target.value)}
            />
          </label>
        </div>
      )}
      <button type="button" className="confirm" onClick={generate} disabled={generating}>
        Generate loop
      </button>
      {generating && (
        <p className="status" role="status">
          Generating: asking HeiGIT for up to 5 loops and checking each one…
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {run?.status === "failed" && (
        <p className="error" role="alert">
          {run.error?.message ?? "Generation failed."}
        </p>
      )}
      {run?.status === "no_route" && (
        <div className="error" role="alert">
          <p>
            No acceptable loop between {km(run.bounds.min_m)} and {km(run.bounds.max_m)} after{" "}
            {run.candidates.length} tries.
          </p>
          <ul>
            {run.candidates.map((candidate) => (
              <li key={candidate.position}>{candidate.reasons.join("; ")}</li>
            ))}
          </ul>
        </div>
      )}
      {run && route && (
        <div className="result" role="status">
          <p className="distance-measured">
            <strong>{km(route.distance_m)}</strong> loop ({route.deviation_m >= 0 ? "+" : "−"}
            {Math.abs(Math.round(route.deviation_m))} m from {km(route.target_m)}; accepted{" "}
            {km(route.bounds.min_m)} to {km(route.bounds.max_m)})
          </p>
          <p>Walking time {minutes(route.walking_duration_s)} (not a running time)</p>
          <ul className="limitations" aria-label="Limitations">
            {route.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
          <details>
            <summary>
              {run.candidates.length} {run.candidates.length === 1 ? "try" : "tries"}
            </summary>
            <ul>
              {run.candidates.map((candidate) => (
                <li key={candidate.position}>
                  {candidate.method === "round_trip" ? `Seed ${candidate.seed}` : "Via loop"}:{" "}
                  {candidate.accepted ? "accepted" : candidate.reasons.join("; ")}
                </li>
              ))}
            </ul>
          </details>
          <a className="download" href={gpxUrl(run.id)} download>
            Download GPX
          </a>
          <p className="address">{route.attribution}</p>
        </div>
      )}
    </div>
  );
}
