import type {
  CompanyTier,
  Seniority,
  SessionState,
  TurnResponse,
} from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

async function http<T>(
  path: string,
  init?: RequestInit & { json?: unknown }
): Promise<T> {
  const headers: Record<string, string> = {
    accept: "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  let body: BodyInit | undefined = (init?.body as BodyInit | undefined) ?? undefined;
  if (init?.json !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const res = await fetch(`${BASE}${path}`, { ...init, headers, body });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const err = await res.json();
      detail = err.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export interface CreateSessionPayload {
  resume_text: string;
  target_company_tier: CompanyTier;
  target_seniority: Seniority;
}

export const api = {
  createSession: (payload: CreateSessionPayload) =>
    http<{ session_id: string; status: string }>("/api/sessions", {
      method: "POST",
      json: payload,
    }),

  uploadResume: async (
    sessionId: string,
    file: File,
    tier: CompanyTier,
    seniority: Seniority
  ) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("target_company_tier", tier);
    fd.append("target_seniority", seniority);
    return http<{ session_id: string; char_count: number }>(
      `/api/sessions/${sessionId}/upload`,
      { method: "POST", body: fd }
    );
  },

  scan: (sessionId: string) =>
    http<SessionState>(`/api/sessions/${sessionId}/scan`, { method: "POST" }),

  selectQuestions: (sessionId: string, questionIds: string[]) =>
    http<SessionState>(`/api/sessions/${sessionId}/select`, {
      method: "POST",
      json: { question_ids: questionIds },
    }),

  getState: (sessionId: string) =>
    http<SessionState>(`/api/sessions/${sessionId}`),

  beginTurn: (sessionId: string) =>
    http<TurnResponse>(`/api/sessions/${sessionId}/turn/begin`, {
      method: "POST",
    }),

  submitAnswer: (sessionId: string, answer: string) =>
    http<TurnResponse>(`/api/sessions/${sessionId}/turn/answer`, {
      method: "POST",
      json: { answer },
    }),

  skipQuestion: (sessionId: string) =>
    http<TurnResponse>(`/api/sessions/${sessionId}/turn/skip`, {
      method: "POST",
    }),

  finish: (sessionId: string) =>
    http<SessionState>(`/api/sessions/${sessionId}/finish`, { method: "POST" }),
};

export function newSessionId(): string {
  // 12-char hex id matching the backend's format. Not cryptographic — just a
  // stable client-side handle for the upload endpoint.
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
