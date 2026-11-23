// Calls to the route API. The types are generated from its OpenAPI document (npm run types).
import type { components } from "./api-types";

export type Candidate = components["schemas"]["Candidate"];
export type PlaceSearchResponse = components["schemas"]["PlaceSearchResponse"];
export type RouteRequest = components["schemas"]["RouteRequest"];
export type RouteRequestCreate = components["schemas"]["RouteRequestCreate"];
export type Activity = RouteRequestCreate["activity"];
export type ErrorResponse = components["schemas"]["ErrorResponse"];

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
    headers: { "Content-Type": "application/json" },
  });
  const body = await response.json();
  if (!response.ok) {
    const error = (body as ErrorResponse).error;
    throw new ApiError(error.code, error.message);
  }
  return body as T;
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
