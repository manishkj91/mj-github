"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { QuestionPlanItem, SessionState, TurnResponse } from "@/lib/types";

interface ChatLine {
  id: string;
  role: "interviewer" | "candidate";
  text: string;
  meta?: { theme?: string; isFollowup?: boolean };
}

export default function InterviewPage({
  params,
}: {
  params: { id: string };
}) {
  const router = useRouter();
  const [state, setState] = useState<SessionState | null>(null);
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [draft, setDraft] = useState("");
  const [awaitingAnswer, setAwaitingAnswer] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    api
      .getState(params.id)
      .then(async (s) => {
        setState(s);
        if (s.status === "complete") {
          router.replace(`/sessions/${params.id}/summary`);
          return;
        }
        await beginNext(s);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [lines, busy]);

  function findQuestion(s: SessionState, qid: string): QuestionPlanItem | null {
    return s.scan?.question_plan.find((q) => q.id === qid) ?? null;
  }

  function appendInterviewer(s: SessionState, t: TurnResponse) {
    const q = findQuestion(s, t.question_id);
    setLines((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "interviewer",
        text: t.utterance,
        meta: {
          theme: q?.theme ?? t.question_theme,
          isFollowup: t.is_followup,
        },
      },
    ]);
  }

  async function beginNext(s: SessionState) {
    setBusy(true);
    setError(null);
    try {
      const t = await api.beginTurn(s.session_id);
      if (t.kind === "interviewer_utterance") {
        appendInterviewer(s, t);
        setAwaitingAnswer(true);
      } else {
        setDone(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to begin question.");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!state || !draft.trim()) return;
    const text = draft.trim();
    setLines((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "candidate", text },
    ]);
    setDraft("");
    setAwaitingAnswer(false);
    setBusy(true);
    setError(null);
    try {
      const t = await api.submitAnswer(state.session_id, text);
      if (t.kind === "interviewer_utterance") {
        appendInterviewer(state, t);
        setAwaitingAnswer(true);
      } else if (t.kind === "question_finished") {
        await beginNext(state);
      } else {
        setDone(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to submit answer.");
    } finally {
      setBusy(false);
    }
  }

  async function skipRest() {
    if (!state) return;
    setBusy(true);
    setError(null);
    try {
      const t = await api.skipQuestion(state.session_id);
      if (t.kind === "session_complete") {
        setDone(true);
      } else {
        await beginNext(state);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to skip.");
    } finally {
      setBusy(false);
      setAwaitingAnswer(false);
    }
  }

  async function finishSession() {
    if (!state) return;
    setBusy(true);
    try {
      await api.finish(state.session_id);
      router.push(`/sessions/${state.session_id}/summary`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to finish.");
      setBusy(false);
    }
  }

  if (!state) {
    return <div className="py-12 text-sm text-ink-500">Loading…</div>;
  }

  const totalQuestions = state.selected_question_ids.length;
  const progress = Math.min(state.current_question_index, totalQuestions);

  return (
    <div className="grid gap-6 md:grid-cols-[3fr_1fr]">
      <section className="flex h-[70vh] flex-col card !p-0">
        <header className="flex items-center justify-between border-b border-ink-100 px-4 py-3">
          <div className="text-sm text-ink-500">
            Question{" "}
            <span className="font-medium text-ink-800">
              {Math.min(progress + 1, totalQuestions)}
            </span>{" "}
            of {totalQuestions}
          </div>
          <button
            type="button"
            className="btn-ghost"
            onClick={skipRest}
            disabled={busy || done}
          >
            Skip follow-ups →
          </button>
        </header>

        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
          {lines.map((l) => (
            <ChatBubble key={l.id} line={l} />
          ))}
          {busy && !awaitingAnswer && <Typing />}
        </div>

        <footer className="border-t border-ink-100 p-3">
          {done ? (
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-ink-500">
                Interview complete. Generate evaluations and the session summary?
              </p>
              <button
                type="button"
                className="btn-primary"
                onClick={finishSession}
                disabled={busy}
              >
                {busy ? "Scoring…" : "See my evaluation →"}
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              <textarea
                className="block h-28 w-full"
                placeholder={
                  awaitingAnswer
                    ? "Type your answer. Lead with the headline result."
                    : "Waiting for the interviewer…"
                }
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled={!awaitingAnswer || busy}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    submit();
                  }
                }}
              />
              <div className="flex items-center justify-between text-xs text-ink-400">
                <span>⌘/Ctrl + Enter to send</span>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={submit}
                  disabled={!awaitingAnswer || busy || draft.trim().length === 0}
                >
                  Send answer
                </button>
              </div>
            </div>
          )}
          {error && (
            <div className="mt-2 rounded-md bg-red-50 p-2 text-xs text-red-700">
              {error}
            </div>
          )}
        </footer>
      </section>

      <aside className="space-y-4 text-sm">
        <div className="card">
          <div className="text-xs uppercase tracking-wide text-ink-400">
            Tips
          </div>
          <ul className="mt-2 space-y-2 prose-lite">
            <li>Lead with the headline metric in the first sentence.</li>
            <li>
              Use &ldquo;I&rdquo; for what you did, &ldquo;we&rdquo; for the team. Be honest about both.
            </li>
            <li>Aim for ~90 seconds per answer; cut context, not impact.</li>
          </ul>
        </div>
        <div className="card">
          <div className="text-xs uppercase tracking-wide text-ink-400">
            Session
          </div>
          <p className="mt-2">
            <span className="tag">{state.target_company_tier}</span>{" "}
            <span className="tag">{state.target_seniority}</span>
          </p>
          <p className="mt-3 text-xs text-ink-400">
            id: <code>{state.session_id}</code>
          </p>
        </div>
      </aside>
    </div>
  );
}

function ChatBubble({ line }: { line: ChatLine }) {
  const isInterviewer = line.role === "interviewer";
  return (
    <div
      className={`flex animate-fade-up ${
        isInterviewer ? "justify-start" : "justify-end"
      }`}
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
          isInterviewer
            ? "bg-ink-100 text-ink-900"
            : "bg-ink-900 text-white"
        }`}
      >
        {isInterviewer && line.meta?.theme && (
          <div className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">
            {line.meta.isFollowup ? "↪ follow-up" : line.meta.theme.replace(/_/g, " ")}
          </div>
        )}
        <p className="whitespace-pre-wrap leading-relaxed">{line.text}</p>
      </div>
    </div>
  );
}

function Typing() {
  return (
    <div className="flex justify-start">
      <div className="rounded-2xl bg-ink-100 px-4 py-3">
        <span className="inline-flex gap-1">
          <Dot delay={0} />
          <Dot delay={120} />
          <Dot delay={240} />
        </span>
      </div>
    </div>
  );
}

function Dot({ delay }: { delay: number }) {
  return (
    <span
      className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-500"
      style={{ animationDelay: `${delay}ms` }}
    />
  );
}
