"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { SessionState } from "@/lib/types";

export default function PlanPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [state, setState] = useState<SessionState | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getState(params.id)
      .then((s) => {
        setState(s);
        const ids = (s.scan?.question_plan ?? []).slice(0, 5).map((q) => q.id);
        setSelected(new Set(ids));
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [params.id]);

  async function startInterview() {
    if (!state) return;
    setBusy(true);
    setError(null);
    try {
      await api.selectQuestions(state.session_id, Array.from(selected));
      router.push(`/sessions/${state.session_id}/interview`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start interview.");
      setBusy(false);
    }
  }

  if (!state) {
    return <div className="py-12 text-sm text-ink-500">Loading…</div>;
  }
  const plan = state.scan?.question_plan ?? [];
  const profile = state.scan?.candidate_profile;

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-8 animate-fade-up">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Question plan</h1>
        <p className="mt-2 max-w-prose text-sm prose-lite">
          The scanner drafted {plan.length} questions for a{" "}
          <span className="tag">{state.target_company_tier}</span>{" "}
          <span className="tag">{state.target_seniority}</span> loop. Pick the
          ones you want to practice. Each selected question may include up to
          two follow-up probes.
        </p>
      </header>

      {profile && (
        <div className="card">
          <div className="text-xs uppercase tracking-wide text-ink-400">
            What the scanner read
          </div>
          <div className="mt-2 grid gap-2 text-sm sm:grid-cols-3">
            <div>
              <span className="font-medium">{profile.roles.length}</span> roles
            </div>
            <div>
              <span className="font-medium">{profile.metrics.length}</span> metrics
            </div>
            <div>
              <span className="font-medium">{profile.domains.length}</span> domains
            </div>
          </div>
          {profile.roles.length > 0 && (
            <ul className="mt-3 text-xs text-ink-500">
              {profile.roles.slice(0, 4).map((r, i) => (
                <li key={i}>
                  {r.title} · {r.company}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <ul className="space-y-3">
        {plan.map((q, i) => {
          const checked = selected.has(q.id);
          return (
            <li key={q.id}>
              <label
                className={`flex cursor-pointer gap-4 rounded-xl bg-white p-4 ring-1 transition ${
                  checked
                    ? "ring-ink-900"
                    : "ring-ink-100 hover:ring-ink-300"
                }`}
              >
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 accent-ink-900"
                  checked={checked}
                  onChange={() => toggle(q.id)}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs text-ink-400">#{i + 1}</span>
                    <span className="tag">{q.theme.replace(/_/g, " ")}</span>
                    {q.is_gap_probe && (
                      <span className="tag-accent">gap probe</span>
                    )}
                  </div>
                  <p className="mt-2 font-medium leading-snug text-ink-900">
                    {q.question_text}
                  </p>
                  <p className="mt-1 text-xs text-ink-500">
                    {q.why_this_question}
                  </p>
                  {q.resume_citation && (
                    <p className="mt-2 border-l-2 border-ink-200 pl-3 text-xs italic text-ink-500">
                      &ldquo;{q.resume_citation.span}&rdquo;
                    </p>
                  )}
                </div>
              </label>
            </li>
          );
        })}
      </ul>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      <div className="sticky bottom-4 flex items-center justify-between gap-4 rounded-xl bg-white/95 p-3 shadow ring-1 ring-ink-100 backdrop-blur">
        <div className="text-sm text-ink-500">
          {selected.size} selected · ~{selected.size * 60}s of feedback per
          question
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={startInterview}
          disabled={busy || selected.size === 0}
        >
          {busy ? "Starting…" : "Start interview →"}
        </button>
      </div>
    </div>
  );
}
