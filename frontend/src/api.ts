import type { Backends, FollowupAnswer, Overview } from "./types";

async function post<T>(url: string, body: unknown): Promise<T> {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || "Request failed");
  return data as T;
}

export function getBackends(): Promise<Backends> {
  return fetch("/api/backends").then((r) => r.json());
}

export function explain(query: string, backend: string): Promise<Overview> {
  return post<Overview>("/api/explain", { query, backend });
}

export function followup(question: string, backend: string): Promise<FollowupAnswer> {
  return post<FollowupAnswer>("/api/followup", { question, backend });
}