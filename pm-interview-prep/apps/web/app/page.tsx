"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, newSessionId } from "@/lib/api";
import type { CompanyTier, Seniority } from "@/lib/types";

const SAMPLE_RESUME = `Senior Product Manager, Stripe — 2022 to Present
- Owned Connect onboarding for the Americas region; team of 4 engineers, 1 designer.
- Led the redesign of the merchant KYC flow; lifted activation from 38% to 51% in 6 weeks (+13pp).
- Drove a contentious deprecation of legacy webhooks across 3 partner teams; shipped on schedule.
- Mentored 2 APMs; both promoted within 12 months.

Product Manager, Square — 2019 to 2022
- Owned the Cash App for Business onboarding funnel; cut median time-to-first-payment by 42%.
- Sunset a $4M/yr SMB lending pilot after a 90-day discovery sprint; reallocated budget to receivables.
`;

export default function HomePage() {
  const router = useRouter();
  const [tier, setTier] = useState<CompanyTier>("faang");
  const [seniority, setSeniority] = useState<Seniority>("senior");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setError(null);
    setBusy(true);
    try {
      let sessionId: string;
      if (file) {
        sessionId = newSessionId();
        await api.uploadResume(sessionId, file, tier, seniority);
      } else {
        const body = text.trim().length > 0 ? text : SAMPLE_RESUME;
        const res = await api.createSession({
          resume_text: body,
          target_company_tier: tier,
          target_seniority: seniority,
        });
        sessionId = res.session_id;
      }
      router.push(`/sessions/${sessionId}/scanning`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start session.");
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-10 md:grid-cols-[3fr_2fr]">
      <section>
        <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
          Practice the behavioral round.
        </h1>
        <p className="mt-3 max-w-prose prose-lite">
          Upload your resume and an AI interviewer will run a tailored
          behavioral session — five questions grounded in your actual work,
          probing follow-ups, and rubric-based feedback for each answer.
        </p>

        <div className="mt-8 card space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="text-sm font-medium">Target company tier</span>
              <select
                className="mt-1 w-full"
                value={tier}
                onChange={(e) => setTier(e.target.value as CompanyTier)}
              >
                <option value="faang">FAANG (Amazon, Google, Meta…)</option>
                <option value="growth">Growth-stage (Stripe, Notion, Linear…)</option>
                <option value="ai_native">AI-native (OpenAI, Anthropic…)</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium">Seniority</span>
              <select
                className="mt-1 w-full"
                value={seniority}
                onChange={(e) => setSeniority(e.target.value as Seniority)}
              >
                <option value="apm">APM</option>
                <option value="pm">PM</option>
                <option value="senior">Senior PM</option>
                <option value="gpm">Group PM</option>
              </select>
            </label>
          </div>

          <div>
            <label className="block">
              <span className="text-sm font-medium">Upload resume (PDF, DOCX, TXT)</span>
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md"
                className="mt-1 block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-ink-900 file:px-3 file:py-2 file:text-sm file:text-white"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <div className="mt-3 text-xs text-ink-400">
              or paste resume text below
            </div>
            <textarea
              className="mt-2 block h-40 w-full"
              placeholder="Paste resume text here…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={!!file}
            />
          </div>

          {error && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex items-center justify-between">
            <button
              type="button"
              className="btn-ghost"
              onClick={() => {
                setFile(null);
                setText(SAMPLE_RESUME);
              }}
            >
              Use sample resume
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={start}
              disabled={busy}
            >
              {busy ? "Starting…" : "Start session →"}
            </button>
          </div>
        </div>
      </section>

      <aside className="space-y-5 md:pt-2">
        <div className="card">
          <h2 className="text-sm font-semibold text-ink-900">
            How it works
          </h2>
          <ol className="mt-3 space-y-3 text-sm prose-lite">
            <li>
              <span className="font-medium text-ink-800">1. Resume Scanner Agent</span>
              {" "}reads your resume and proposes 5–8 questions, each grounded in a
              specific project or metric you wrote down.
            </li>
            <li>
              <span className="font-medium text-ink-800">2. Interview Agent</span>{" "}
              asks one question at a time and probes for STAR depth with up to two
              follow-ups.
            </li>
            <li>
              <span className="font-medium text-ink-800">3. Evaluation Agent</span>{" "}
              scores each answer on structure, specificity, ownership, impact,
              reflection, and communication, and rewrites a stronger version of
              your story.
            </li>
          </ol>
        </div>

        <div className="card text-sm prose-lite">
          <p>
            <span className="tag-accent">Privacy</span>
            <span className="ml-2">
              Resumes are PII-redacted before any LLM call and live only in the
              backend&rsquo;s process memory. Nothing is persisted to disk.
            </span>
          </p>
        </div>
      </aside>
    </div>
  );
}
