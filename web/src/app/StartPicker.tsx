"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import {
  type Activity,
  ApiError,
  type Candidate,
  createRouteRequest,
  getRouteRequest,
  type PlaceSearchResponse,
  type RouteRequest,
  type RouteRequestCreate,
  searchPlaces,
} from "@/api";

import RunPanel from "./RunPanel";

// Leaflet needs the browser's window, so the map is only rendered client-side.
const StartMap = dynamic(() => import("./StartMap"), { ssr: false });

const SEARCH_DELAY_MS = 400;

type Search = { query: string; response?: PlaceSearchResponse; error?: string };
type Selection =
  | { kind: "named"; query: string; candidate: Candidate }
  | { kind: "map"; point: [number, number] };

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "The route API could not be reached.";
}

function selectionPoint(selection: Selection | null): [number, number] | null {
  if (selection === null) {
    return null;
  }
  if (selection.kind === "map") {
    return selection.point;
  }
  return selection.candidate.point.coordinates;
}

export default function StartPicker() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<Search | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [activity, setActivity] = useState<Activity>("running");
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<RouteRequest | null>(null);
  const [route, setRoute] = useState<[number, number][] | null>(null);
  const trimmed = query.trim();

  useEffect(() => {
    if (trimmed.length < 2) {
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await searchPlaces(trimmed, controller.signal);
        setSearch({ query: trimmed, response });
      } catch (error) {
        if (!controller.signal.aborted) {
          setSearch({ query: trimmed, error: describeError(error) });
        }
      }
    }, SEARCH_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [trimmed]);

  function choose(next: Selection) {
    setSelection(next);
    setConfirmed(null);
    setRoute(null);
    setConfirmError(null);
  }

  function pickOnMap(point: [number, number]) {
    choose({ kind: "map", point });
  }

  async function confirm() {
    if (selection === null) {
      return;
    }
    let start: RouteRequestCreate["start"];
    if (selection.kind === "named") {
      start = { kind: "named", query: selection.query, source_id: selection.candidate.source_id };
    } else {
      start = { kind: "map", point: { type: "Point", coordinates: selection.point } };
    }
    setConfirming(true);
    setConfirmError(null);
    try {
      const created = await createRouteRequest({ activity, start });
      setConfirmed(await getRouteRequest(created.id));
    } catch (error) {
      setConfirmError(describeError(error));
    } finally {
      setConfirming(false);
    }
  }

  const current = search !== null && search.query === trimmed ? search : null;
  const searching = trimmed.length >= 2 && current === null;

  return (
    <div className="layout">
      <section className="panel">
        <label htmlFor="place">Search for a place, or tap the map</label>
        <input
          id="place"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. Avenue South Residence"
          autoComplete="off"
          maxLength={120}
        />
        {searching && <p className="status">Searching…</p>}
        {current?.error && (
          <p className="error" role="alert">
            {current.error}
          </p>
        )}
        {current?.response?.outcome === "no_match" && (
          <p className="status">No place in Singapore matches “{current.query}”.</p>
        )}
        {current?.response && current.response.candidates.length > 0 && (
          <>
            <p className="status">
              {current.response.candidates.length === 1
                ? "One match. Check it is the right place."
                : `${current.response.candidates.length} matches. Choose the right one.`}
              {current.response.more_results && " More exist: add detail to narrow them."}
            </p>
            <ul className="candidates" aria-label="Matching places">
              {current.response.candidates.map((candidate) => (
                <li key={candidate.source_id}>
                  <button
                    type="button"
                    aria-pressed={
                      selection?.kind === "named" &&
                      selection.candidate.source_id === candidate.source_id
                    }
                    onClick={() => choose({ kind: "named", query: current.query, candidate })}
                  >
                    <strong>{candidate.name}</strong>
                    <span>{candidate.address}</span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}

        {selection && (
          <div className="selection">
            <h2>Start</h2>
            {selection.kind === "named" ? (
              <p>
                {selection.candidate.name}
                <br />
                <span className="address">{selection.candidate.address}</span>
              </p>
            ) : (
              <p>
                Selected map point
                <br />
                <span className="address">
                  {selection.point[1].toFixed(5)}, {selection.point[0].toFixed(5)}
                </span>
              </p>
            )}
            <fieldset>
              <legend>Activity</legend>
              <label>
                <input
                  type="radio"
                  name="activity"
                  checked={activity === "running"}
                  onChange={() => setActivity("running")}
                />
                Running
              </label>
              <label>
                <input
                  type="radio"
                  name="activity"
                  checked={activity === "road_cycling"}
                  onChange={() => setActivity("road_cycling")}
                />
                Road cycling
              </label>
            </fieldset>
            <button type="button" className="confirm" onClick={confirm} disabled={confirming}>
              Confirm start
            </button>
            {confirmError && (
              <p className="error" role="alert">
                {confirmError}
              </p>
            )}
          </div>
        )}

        {confirmed && (
          <div className="confirmed" role="status">
            <h2>Start confirmed</h2>
            <p>
              {confirmed.start.name ?? "Map point"} for{" "}
              {confirmed.activity === "running" ? "running" : "road cycling"}
            </p>
            <p className="address">
              {confirmed.start.source === "onemap" ? "Source: OneMap" : "Source: map selection"}
              {" · "}
              {confirmed.start.point.coordinates[1].toFixed(5)},{" "}
              {confirmed.start.point.coordinates[0].toFixed(5)}
            </p>
          </div>
        )}

        {confirmed && <RunPanel routeRequest={confirmed} onRoute={setRoute} />}
      </section>
      <div className="map-wrap">
        <StartMap point={selectionPoint(selection)} route={route} onPick={pickOnMap} />
      </div>
    </div>
  );
}
