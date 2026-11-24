// Calls to the route API. The types are generated from its OpenAPI document (npm run types).
import type { components } from "./api-types";

export type Candidate = components["schemas"]["Candidate"];
export type PlaceSearchResponse = components["schemas"]["PlaceSearchResponse"];
export type RouteRequest = components["schemas"]["RouteRequest"];
export type RouteRequestCreate = components["schemas"]["RouteRequestCreate"];
export type Activity = RouteRequestCreate["activity"];
export type ErrorResponse = components["schemas"]["ErrorResponse"];
export type SignedIn = components["schemas"]["SignedIn"];

// The API refuses any change that does not echo the session's CSRF token.
let csrfToken = "";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
  });
  const body = await response.json();
  if (!response.ok) {
    const error = (body as ErrorResponse).error;
    throw new ApiError(error.code, error.message);
  }
  return body as T;
}

export const SIGN_IN_URL = "/api/auth/login";

// The signed-in owner, or null when the browser has no session yet.
export async function getSignedIn(): Promise<SignedIn | null> {
  try {
    const signedIn = await call<SignedIn>("/api/auth/me", { method: "GET" });
    csrfToken = signedIn.csrf_token;
    return signedIn;
  } catch (error) {
    if (error instanceof ApiError && error.code === "not_signed_in") {
      return null;
    }
    throw error;
  }
}

export async function signOut(): Promise<void> {
  const response = await fetch("/api/auth/logout", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
  });
  if (!response.ok) {
    const error = ((await response.json()) as ErrorResponse).error;
    throw new ApiError(error.code, error.message);
  }
  csrfToken = "";
}

export function searchPlaces(query: string, signal: AbortSignal): Promise<PlaceSearchResponse> {
  return call("/api/places/search", { method: "POST", body: JSON.stringify({ query }), signal });
}

export function createRouteRequest(request: RouteRequestCreate): Promise<RouteRequest> {
  return call("/api/route-requests", { method: "POST", body: JSON.stringify(request) });
}

export function getRouteRequest(id: string): Promise<RouteRequest> {
  return call(`/api/route-requests/${id}`, { method: "GET" });
}

export type Distance = components["schemas"]["RunCreate"]["distance"];
export type GenerationRun = components["schemas"]["GenerationRun"];
export type SelectedRoute = components["schemas"]["SelectedRoute"];

// Sending the same operation ID again (after a lost response) returns the same run.
export function startRun(
  routeRequestId: string,
  operationId: string,
  distance: Distance,
): Promise<GenerationRun> {
  return call(`/api/route-requests/${routeRequestId}/runs`, {
    method: "POST",
    body: JSON.stringify({ operation_id: operationId, distance }),
  });
}

export function getRun(runId: string): Promise<GenerationRun> {
  return call(`/api/runs/${runId}`, { method: "GET" });
}

export function getSelectedRoute(runId: string): Promise<SelectedRoute> {
  return call(`/api/runs/${runId}/route`, { method: "GET" });
}

export function gpxUrl(runId: string): string {
  return `/api/runs/${runId}/route.gpx`;
}

export type AgentAnswer = components["schemas"]["AgentAnswer"];
export type AgentStep = components["schemas"]["AgentStep"];

// One synchronous request: the answer comes back once it is judged (or written from facts).
export function askAssistant(
  routeRequestId: string,
  brief: string,
  distance: Distance | null,
): Promise<AgentAnswer> {
  return call(`/api/route-requests/${routeRequestId}/agent-runs`, {
    method: "POST",
    body: JSON.stringify({ brief, distance }),
  });
}
