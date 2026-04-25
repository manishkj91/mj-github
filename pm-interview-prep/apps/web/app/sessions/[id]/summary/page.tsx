"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SessionState } from "@/lib/types";

export default function SummaryPage({ params }: { params: { id: string } }) {
  const [state, setState] = useState<SessionState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getState(params.id)
      .then((s) => {
        if (s.status !== "complete") {
          // Trigger evaluations + summary if the user navigated here directly.
          return api.finish(params.id).then(setState);
        }
        setState(s);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [params.id]);

  if (error) {
    return (
      <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }
  if (!state || !state.summary) {
    return <div className="py-12 text-sm text-ink-500">Compiling your session report…</div>;
  }

  const summary = state.summary;
  const evaluations = Object.entries(state.evaluations);

  return (
    <div className="space-y-10 animate-fade-up">
      <header>
        <div className="text-xs uppercase tracking-wide text-ink-400">
          Session report
        </div>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">
          Here&rsquo;s how that went.
        </h1>
        <p className="mt-2 max-w-prose text-sm prose-lite">
          Average rubric scores by theme, the stories worth keeping, and three
          concrete things to practice before your next session.
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="card">
          <h2 className="text-sm font-semibold">Competency heatmap</h2>
          <ul className="mt-4 space-y-2">
            {summary.competency_heatmap.map((h) => (
              <li key={h.theme} className="flex items-center gap-3">
                <span className="w-44 truncate text-sm text-ink-700">
                  {h.theme.replace(/_/g, " ")}
                </span>
                <div className="h-2 flex-1 rounded-full bg-ink-100">
                  <div
                    className="h-2 rounded-full bg-ink-900"
                    style={{ width: `${(h.score / 5) * 100}%` }}
                  />
                </div>
                <span className="w-10 text-right text-sm tabular-nums">
                  {h.score.toFixed(1)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h2 className="text-sm font-semibold">Top recommendations</h2>
          <ol className="mt-3 space-y-3 text-sm prose-lite">
            {summary.top_recommendations.map((r, i) => (
              <li key={i}>
                <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-ink-900 text-[10px] font-semibold text-white">
                  {i + 1}
                </span>
                {r}
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="card">
          <h2 className="text-sm font-semibold">Stories to keep</h2>
          <ul className="mt-3 space-y-2 text-sm prose-lite">
            {summary.keep_stories.map((s, i) => (
              <li key={i}>• {s}</li>
            ))}
            {summary.keep_stories.length === 0 && (
              <li className="text-ink-400">None yet.</li>
            )}
          </ul>
        </div>
        <div className="card">
          <h2 className="text-sm font-semibold">Stories to rework</h2>
          <ul className="mt-3 space-y-2 text-sm prose-lite">
            {summary.rework_stories.map((s, i) => (
              <li key={i}>• {s}</li>
            ))}
            {summary.rework_stories.length === 0 && (
              <li className="text-ink-400">Nothing flagged.</li>
            )}
          </ul>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">
          Per-question feedback
        </h2>
        {evaluations.map(([qid, ev]) => {
          const q = state.scan?.question_plan.find((x) => x.id === qid);
          if (!q) return null;
          const avg = (
            (ev.rubric_scores.structure +
              ev.rubric_scores.specificity +
              ev.rubric_scores.ownership +
              ev.rubric_scores.impact +
              ev.rubric_scores.reflection +
              ev.rubric_scores.communication) /
            6
          ).toFixed(1);
          return (
            <article key={qid} className="card">
              <div className="flex flex-wrap items-center gap-2">
                <span className="tag">{q.theme.replace(/_/g, " ")}</span>
                <span className="text-xs text-ink-500">
                  avg <span className="font-semibold text-ink-800">{avg}</span> / 5
                </span>
              </div>
              <h3 className="mt-2 font-medium">{q.question_text}</h3>

              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                    What worked
                  </div>
                  <ul className="mt-1 space-y-1 text-sm prose-lite">
                    {ev.what_worked.map((w, i) => (
                      <li key={i}>• {w}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-amber-700">
                    What to improve
                  </div>
                  <ul className="mt-1 space-y-1 text-sm prose-lite">
                    {ev.what_to_improve.map((w, i) => (
                      <li key={i}>• {w}</li>
                    ))}
                  </ul>
                </div>
              </div>

              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-medium text-ink-700">
                  Stronger rewrite of this story
                </summary>
                <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-ink-50 p-3 text-sm leading-relaxed text-ink-800">
                  {ev.model_answer}
                </pre>
              </details>

              <p className="mt-4 text-sm">
                <span className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                  Practice next:{" "}
                </span>
                {ev.revision_task}
              </p>

              <ScoreGrid scores={ev.rubric_scores} />
            </article>
          );
        })}
      </section>

      <div className="flex justify-end">
        <a className="btn-secondary" href="/">
          Start a new session
        </a>
      </div>
    </div>
  );
}

function ScoreGrid({
  scores,
}: {
  scores: import("@/lib/types").RubricScores;
}) {
  const entries: [string, number][] = [
    ["structure", scores.structure],
    ["specificity", scores.specificity],
    ["ownership", scores.ownership],
    ["impact", scores.impact],
    ["reflection", scores.reflection],
    ["communication", scores.communication],
  ];
  return (
    <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-6">
      {entries.map(([k, v]) => (
        <div
          key={k}
          className="rounded-md bg-ink-50 px-2 py-1 text-center"
        >
          <div className="text-[10px] uppercase tracking-wider text-ink-500">
            {k}
          </div>
          <div className="text-sm font-semibold tabular-nums">{v}/5</div>
        </div>
      ))}
    </div>
  );
}
